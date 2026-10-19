"""Visual routes preserve source pages and require explicit review before model creation."""
import base64
import copy
import io

import pytest
from PIL import Image

from apps.helios.tests.test_materials_api import client, path
from helios_core.demo import materials
from helios_core.demo.visual_documents import _validate


ROW = {'page': 1, 'entity': 'Example', 'metric': 'Revenue', 'value': 12.0,
       'unit': 'USD', 'period': '2025', 'population': 'All customers', 'denominator': None,
       'source_quote': 'Revenue 12 USD', 'extraction_kind': 'chart', 'uncertainty': 'Chart estimate'}


def png_upload(http, **changes):
    output = io.BytesIO()
    Image.new('RGB', (16, 20), changes.pop('color', 'white')).save(output, format='PNG')
    response = http.post('/demo/api/materials/upload', json={
        'filename': 'chart.png', 'content_base64': base64.b64encode(output.getvalue()).decode(), **changes})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def extracted(client, monkeypatch):
    http, app, llm = client
    monkeypatch.setattr(materials, 'extract_visual', lambda *args: _validate({
        'summary': 'Revenue chart', 'transcripts': [{'page': 1, 'text': 'Revenue 12 USD'}],
        'observations': [copy.deepcopy(ROW)]}, [1]))
    # Image uploads are transcribed automatically with the draft model.
    item = png_upload(http)
    assert item['revision'] == 1 and item['status'] == 'visual_review_required'
    assert item['ocr_notice'].startswith('AI transcribed page(s) 1.')
    return http, app, llm, item


def facts(item, **changes):
    return {'revision': item['revision'], 'extraction_id': item['visual_extraction']['extraction_id'],
            'title': 'Reviewed revenue', 'rows': [ROW | {'id': 'observation_1'}],
            'reviewer': 'API reviewer', 'note': 'Checked against original source chart',
            'acknowledged': True, **changes}


def test_png_preview_revision_and_public_route_allowlist(client):
    http, _, _ = client
    item = png_upload(http)
    assert item['chunks'] == [] and item['status'] == 'visual_pending'
    assert item['visual_source']['page_count'] == 1
    preview = http.get(path(item, 'preview'), params={'revision': 1, 'page': 1})
    assert preview.status_code == 200
    assert preview.content.startswith(b'\x89PNG')
    assert preview.headers['content-type'] == 'image/png'
    assert preview.headers['cache-control'] == 'no-store'
    assert http.get(path(item, 'preview'), params={'revision': 9, 'page': 1}).status_code == 409
    assert http.get(path(item, 'preview'), params={'revision': 1, 'page': 2}).status_code == 409
    assert http.get(path(item, 'preview')).status_code == 422
    for suffix in ['preview/extra', 'visual/extra', 'facts/extra', 'raw']:
        response = http.get(path(item, suffix))
        assert response.status_code == 404
        assert response.json()['detail'] == 'Unavailable in local sample mode'


def test_visual_result_has_unverified_lineage_and_historical_guard(extracted):
    http, _, llm, item = extracted
    assert item['visual_extraction']['review_status'] == 'needs_human_review'
    assert item['visual_extraction']['observations'][0]['verification_status'] == 'visual_unverified'
    assert item['chunks'][0]['verification_status'] == 'visual_unverified'
    assert item['links'] == [] and item.get('fact_models', []) == []
    png_upload(http, document_id=item['document_id'], color='blue')
    assert http.post(path(item, 'visual'), json={'revision': 1, 'pages': [1]}).status_code == 409
    assert http.post(path(item, 'facts'), json=facts(item)).status_code == 409


@pytest.mark.parametrize('pages', [[], list(range(1, 8))])
def test_visual_page_request_limits(client, pages):
    http, _, _ = client
    item = png_upload(http)
    assert http.post(path(item, 'visual'), json={'revision': 1, 'pages': pages}).status_code == 422


def test_visual_invalid_provider_output_never_echoes_credentials(client, monkeypatch):
    http, _, llm = client
    secret = 'PRIVATE-API-TOKEN https://private-provider.test source content'
    llm.api_key = secret
    def fail(*args):
        raise ValueError(secret)
    monkeypatch.setattr(materials, 'extract_visual', fail)
    item = png_upload(http)
    response = http.post(path(item, 'visual'), json={'revision': 1, 'pages': [1]})
    assert response.status_code == 502
    assert secret not in response.text and 'PRIVATE-API-TOKEN' not in response.text
    assert http.get(path(item)).json().get('visual_extraction') is None
    assert secret not in http.get('/demo/api/llm').text


@pytest.mark.parametrize('changes,status', [({'acknowledged': False}, 409), ({'unexpected': 'field'}, 422),
                                           ({'extraction_id': 'f'*64}, 409), ({'reviewer': ' '}, 409)])
def test_facts_acknowledgment_and_strict_schema(extracted, changes, status):
    http, _, _, item = extracted
    before = http.get('/demo/api/hub').json()
    response = http.post(path(item, 'facts'), json=facts(item, **changes))
    assert response.status_code == status, response.text
    assert http.get('/demo/api/hub').json() == before


def test_fact_row_extra_fields_rejected(extracted):
    http, _, _, item = extracted
    row = ROW | {'id': 'observation_1', 'verification_status': 'approved'}
    assert http.post(path(item, 'facts'), json=facts(item, rows=[row])).status_code == 422


def test_reviewed_edited_rows_create_new_source_without_publication(extracted):
    http, app, _, item = extracted
    before = http.get('/demo/api/hub').json()
    row = ROW | {'id': 'observation_1', 'entity': 'Renamed company', 'metric': 'Net revenue',
                 'value': 13.5, 'denominator': 100, 'uncertainty': 'Reviewer corrected chart reading'}
    response = http.post(path(item, 'facts'), json=facts(item, rows=[row]))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['source'].startswith('doc_')
    assert result['source'] in result['studio_url']
    after = http.get('/demo/api/hub').json()
    assert len(after['sources']) == len(before['sources']) + 1
    source = http.get('/demo/api/hub/source', params={'source': result['source']}).json()
    assert source['model']['versions'] == [] and source['model']['active_version'] is None
    context = http.get('/demo/api/context', params={'source': result['source']}).json()
    assert context['versions'] == [] and context['active_version'] is None
    runtime = app.state.demo_hub.runtime(result['source'])
    csv_text = next(table.csv_bytes.decode() for table in runtime.pack.tables if table.name == 'document_observations')
    assert 'Renamed company' in csv_text and 'Net revenue' in csv_text and '13.5' in csv_text
    assert result['document']['fact_models'][0]['reviewer'] == 'API reviewer'
    assert http.post(path(item, 'facts'), json=facts(item)).status_code == 409
    repeated = http.post(path(item, 'visual'), json={'revision': 1, 'pages': [1]})
    assert repeated.status_code == 200
    assert repeated.json()['revision'] == 2
    assert not repeated.json().get('fact_models')
    historical = http.get(path(item, '' ).rstrip('/'), params={'revision': 1}).json()
    assert historical['fact_models'] == result['document']['fact_models']


@pytest.mark.parametrize('changes,status', [({'id': 'observation_999'}, 409), ({'page': 2}, 409),
                                           ({'denominator': -1}, 422), ({'metric': ' '}, 422)])
def test_facts_invalid_observation_fields(extracted, changes, status):
    http, _, _, item = extracted
    row = ROW | {'id': 'observation_1'} | changes
    response = http.post(path(item, 'facts'), json=facts(item, rows=[row]))
    assert response.status_code == status, response.text


def test_mixed_pdf_keeps_text_and_auto_transcribes_scanned_pages(client, monkeypatch):
    from apps.helios.tests.test_document_parser import pdf_bytes
    http, _, _ = client
    calls = []
    def transcribe(filename, data, pages, llm):
        calls.append(pages)
        return _validate({'summary': 'Scan', 'transcripts': [{'page': 2, 'text': 'Scanned maintenance log'}],
                          'observations': []}, pages)
    monkeypatch.setattr(materials, 'extract_visual', transcribe)
    response = http.post('/demo/api/materials/upload', json={
        'filename': 'mixed.pdf', 'content_base64': base64.b64encode(pdf_bytes('Text page', None)).decode()})
    assert response.status_code == 200, response.text
    item = response.json()
    assert calls == [[2]] and item['visual_source']['ocr_pages'] == [2]
    assert [c.get('extraction_method') for c in item['chunks']] == [None, 'vision']
    assert item['chunks'][1]['text'] == 'Scanned maintenance log'


def test_failed_auto_transcription_keeps_the_upload(client):
    http, _, _ = client
    # The test model is not a vision provider, so transcription is refused but the image is stored.
    item = png_upload(http)
    assert item['status'] == 'visual_pending' and item['chunks'] == []
    assert item['ocr_notice'].startswith('Automatic transcription did not run')
