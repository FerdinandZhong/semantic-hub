"""Reviewed visual facts create isolated, durable, typed source models."""
import base64
import copy
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from apps.helios.console.demo_hub import DemoHub
from helios_core.demo.builder_artifacts import BuilderArtifacts
from helios_core.demo.document_facts import FactRow, MaterialFacts, MaterialVisual
from helios_core.demo.materials import MaterialLibrary, MaterialUpload
from helios_core.demo.registry import DemoError, PackRegistry
from helios_core.demo.runtime import DemoRuntime

ROOT = Path(__file__).resolve().parents[3]


def make_hub(state):
    registry = PackRegistry(ROOT/'apps/helios/demo-packs.json', ROOT/'apps/helios-ds-generation/fixtures/sectors/v1')
    return DemoHub(registry, state, DemoRuntime(registry.load('power'), state))


@pytest.fixture
def library(tmp_path):
    hub = make_hub(tmp_path)
    yield MaterialLibrary(hub)
    hub.close()


def image(color='white'):
    stream = io.BytesIO()
    Image.new('RGB', (20, 20), color).save(stream, format='PNG')
    return stream.getvalue()


def upload(library, data=None, filename='clinical.png', document_id=None):
    return library.upload(MaterialUpload(filename=filename, content_base64=base64.b64encode(data or image()).decode(), document_id=document_id))


def extract(library, monkeypatch, item):
    def fake(filename, data, pages, llm):
        if not pages or pages != [1]:
            raise DemoError('Select valid explicit pages')
        return {'summary': 'Clinical endpoints', 'pages': pages, 'transcripts': [{'page': 1, 'text': 'ORR 42% in trial cohort'}],
                'claims': [], 'observations': [dict(page=1, entity='Trial cohort', metric='ORR', value=42.0, unit='%',
                    period='2025', population='Treated patients', denominator=None, source_quote='ORR 42%',
                    extraction_kind='table', uncertainty='Denominator unavailable')], 'review_status': 'needs_human_review'}
    monkeypatch.setattr('helios_core.demo.materials.extract_visual', fake)
    return library.visual(item['document_id'], MaterialVisual(revision=item['revision'], pages=[1]),
                          SimpleNamespace(provider='openai', model='gpt-4o'))


def facts(item, **changes):
    proposed = item['visual_extraction']['observations'][0]
    row = {key: proposed[key] for key in FactRow.model_fields}
    data = dict(revision=item['revision'], extraction_id=item['visual_extraction']['extraction_id'],
                title='Clinical endpoint review', rows=[row], reviewer='Reviewer', note='Checked original source page.', acknowledged=True)
    data.update(changes)
    return MaterialFacts.model_validate(data)


def test_png_original_preview_and_scanned_pdf(library):
    raw = image()
    item = upload(library, raw)
    assert item['status'] == 'visual_pending'
    assert item['visual_source']['page_count'] == 1
    assert library.original(item['document_id'], 1)[1] == raw
    assert library.preview(item['document_id'], 1, 1).startswith(b'\x89PNG')
    stream = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(stream, format='PDF')
    scanned = upload(library, stream.getvalue(), 'scan.pdf')
    assert scanned['status'] == 'visual_pending'
    assert scanned['visual_source']['page_count'] == 1
    assert library.original(scanned['document_id'], 1)[1] == stream.getvalue()


def test_visual_failure_is_atomic_and_requires_explicit_pages(library, monkeypatch):
    item = extract(library, monkeypatch, upload(library))
    before = copy.deepcopy(library.detail(item['document_id']))
    def fail(*args):
        raise DemoError('Fake provider failure')
    monkeypatch.setattr('helios_core.demo.materials.extract_visual', fail)
    with pytest.raises(DemoError, match='provider failure'):
        library.visual(item['document_id'], MaterialVisual(revision=1, pages=[1]), SimpleNamespace(provider='openai', model='gpt-4o'))
    assert library.detail(item['document_id']) == before
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        MaterialVisual(revision=1, pages=[])


@pytest.mark.parametrize('kind', ['acknowledgment', 'stale', 'duplicate', 'unknown', 'unit', 'page'])
def test_fact_review_guards_are_atomic(library, monkeypatch, kind):
    item = extract(library, monkeypatch, upload(library))
    payload = facts(item)
    if kind == 'acknowledgment':
        payload = payload.model_copy(update={'acknowledged': False})
    elif kind == 'stale':
        payload = payload.model_copy(update={'extraction_id': '0' * 64})
    elif kind == 'duplicate':
        payload = payload.model_copy(update={'rows': [payload.rows[0], payload.rows[0]]})
    else:
        changes = {'id': 'observation_999'} if kind == 'unknown' else {'unit': ''} if kind == 'unit' else {'page': 2}
        payload = payload.model_copy(update={'rows': [payload.rows[0].model_copy(update=changes)]})
    sources_before = set(library.hub.registry.entries)
    with pytest.raises(DemoError):
        library.facts(item['document_id'], payload)
    assert set(library.hub.registry.entries) == sources_before
    assert 'fact_models' not in library.detail(item['document_id'])


def test_new_revision_rejects_old_extraction_review(library, monkeypatch):
    item = extract(library, monkeypatch, upload(library))
    revised = upload(library, image('red'), document_id=item['document_id'])
    assert revised['revision'] == 2
    with pytest.raises(DemoError, match='newer document revision'):
        library.facts(item['document_id'], facts(item))


def test_corrected_rows_create_typed_isolated_model_and_lineage(library, monkeypatch):
    item = extract(library, monkeypatch, upload(library))
    payload = facts(item)
    corrected = payload.rows[0].model_copy(update={'value': 43.5, 'denominator': 80.0, 'source_quote': 'ORR 43.5%'})
    payload = payload.model_copy(update={'rows': [corrected]})
    old = copy.deepcopy(library.hub.runtime('manufacturing').workspace.view())
    created = library.facts(item['document_id'], payload)
    runtime = library.hub.runtime(created['source'])
    from helios_core.demo.local import LocalPackEngine
    engine = LocalPackEngine(runtime.pack)
    try:
        rows = engine.query('SELECT value, denominator, source_page, unit, source_quote FROM document_observations').dicts()
        assert rows == [{'value': 43.5, 'denominator': 80.0, 'source_page': 1, 'unit': '%', 'source_quote': 'ORR 43.5%'}]
    finally:
        engine.close()
    definition = runtime.workspace.view()['draft']['definition']
    assert definition['title'] == payload.title
    assert any(m['name'] == 'observation_1_value' for m in definition['metrics'])
    bundle = BuilderArtifacts(runtime.workspace).bundle(definition)
    assert bundle['semantic_layer']['datasets']
    from helios_core.retrieval.index import SemanticIndex
    index = SemanticIndex(bundle['semantic_layer'])
    assert index.bundle('observation_1_value', metric='observation_1_value')['document']['metrics']
    assert 'source_page' in str(bundle['metadata'])
    assert bundle['documents'][0]['source_metadata']['source_sha256'] == item['sha256']
    assert '43.5' in bundle['documents'][0]['content']
    assert '42.0' in bundle['documents'][0]['content']
    assert library.hub.runtime('manufacturing').workspace.view() == old
    assert created['document']['status'] == 'facts_reviewed'
    with pytest.raises(DemoError, match='already created'):
        library.facts(item['document_id'], payload)
    before = library._read(item['document_id'], 1)
    repeated = extract(library, monkeypatch, created['document'])
    assert repeated['revision'] == 2
    assert not repeated.get('fact_models')
    assert library._read(item['document_id'], 1) == before
    assert library.original(item['document_id'], 2)[1] == library.original(item['document_id'], 1)[1]


def test_document_model_survives_hub_restart(library, monkeypatch):
    item = extract(library, monkeypatch, upload(library))
    created = library.facts(item['document_id'], facts(item))
    state = library.hub.state_root
    reloaded = make_hub(state)
    try:
        assert created['source'] in reloaded.registry.entries
        runtime = reloaded.runtime(created['source'])
        assert runtime.pack.entry.data_origin == 'document_evidence'
        assert runtime.workspace.view()['draft']['definition']['title'] == 'Clinical endpoint review'
        persisted = MaterialLibrary(reloaded).detail(item['document_id'])
        assert persisted['fact_models'][0]['source'] == created['source']
    finally:
        reloaded.close()


def test_existing_published_version_remains_immutable(library, monkeypatch):
    from apps.helios.tests.test_demo_context import validated, review_request, publish
    runtime = library.hub.runtime('manufacturing')
    validated(runtime)
    runtime.workspace.review(review_request(runtime))
    publish(runtime)
    release = copy.deepcopy(runtime.workspace.release('v1'))
    item = extract(library, monkeypatch, upload(library))
    library.facts(item['document_id'], facts(item))
    assert runtime.workspace.release('v1') == release


def test_interrupted_creation_freezes_review_and_retries_same_payload(library, monkeypatch):
    item = extract(library, monkeypatch, upload(library))
    payload = facts(item)
    create = library.hub.create_document_model
    def fail(*args):
        raise DemoError('Injected creation failure')
    monkeypatch.setattr(library.hub, 'create_document_model', fail)
    with pytest.raises(DemoError, match='creation failure'):
        library.facts(item['document_id'], payload)
    pending = library.detail(item['document_id'])
    assert pending['status'] == 'fact_creation_pending'
    assert pending['fact_review_pending'] == payload.model_dump(mode='json')
    with pytest.raises(DemoError, match='pending'):
        library.facts(item['document_id'], payload.model_copy(update={'note': 'Changed review decision.'}))
    with pytest.raises(DemoError, match='frozen'):
        extract(library, monkeypatch, pending)
    from helios_core.demo.materials import MaterialAnalyze
    with pytest.raises(DemoError, match='frozen'):
        library.analyze(item['document_id'], MaterialAnalyze(revision=1), SimpleNamespace())
    monkeypatch.setattr(library.hub, 'create_document_model', create)
    completed = library.facts(item['document_id'], payload)
    assert completed['document']['status'] == 'facts_reviewed'
    assert 'fact_review_pending' not in completed['document']


def test_repeated_pages_preserve_reviewed_evidence(library, monkeypatch):
    from helios_core.demo.materials import MaterialSuggest, MaterialReview
    stream = io.BytesIO()
    Image.new('RGB', (20, 20), 'white').save(stream, format='PDF', save_all=True,
        append_images=[Image.new('RGB', (20, 20), 'red')])
    item = extract(library, monkeypatch, upload(library, stream.getvalue(), 'pages.pdf'))
    item = library.suggest(item['document_id'], MaterialSuggest(revision=1, pages=[1]))
    assert item['links']
    item = library.review(item['document_id'], MaterialReview(revision=1,
        link_ids=[item['links'][0]['id']], decision='approved', reviewer='Test reviewer', note='Checked page'))
    # Both actions remain available for the same analyzed revision.
    created = library.facts(item['document_id'], facts(item))
    before = library._read(item['document_id'], 1)
    def page_two(filename, data, pages, llm):
        assert pages == [2]
        return dict(summary='Second page', pages=pages, observations=[], claims=[],
            transcripts=[dict(page=2, text='Manufacturing maintenance planned downtime minutes')])
    monkeypatch.setattr('helios_core.demo.materials.extract_visual', page_two)
    repeated = library.visual(item['document_id'], MaterialVisual(revision=1, pages=[2]),
        SimpleNamespace(provider='openai', model='gpt-4o'))
    assert repeated['revision'] == 2
    assert repeated['visual_extraction']['pages'] == [2]
    assert repeated['links'] == [] and not repeated.get('fact_models')
    assert library._read(item['document_id'], 1) == before
    assert created['source'] in library.hub.registry.entries
    assert all(c['page'] == 2 for c in repeated['chunks'] if c.get('extraction_method') == 'vision')
    scoped = library.suggest(item['document_id'], MaterialSuggest(revision=2, pages=[2]))
    assert scoped['links'] and scoped['matching']['pages'] == [2]
    assert all('page 2' in link['location'] for link in scoped['links'])
    with pytest.raises(DemoError, match='distinct pages'):
        library.suggest(item['document_id'], MaterialSuggest(revision=2, pages=[3]))
