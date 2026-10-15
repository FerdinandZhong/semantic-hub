import io
import json
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from helios_core.demo.registry import DemoError
from helios_core.demo.visual_documents import extract_visual, inspect_visual, render_visual_page
from helios_core.llm import LLMError


def png():
    out = io.BytesIO()
    Image.new('RGB', (16, 12), 'white').save(out, format='PNG')
    return out.getvalue()


def client():
    return SimpleNamespace(provider='openai', api_key='secret-test-key', base_url='https://api.openai.com/v1',
                           model='gpt-4o', timeout=10, max_tokens=4000)


def result(page=1):
    return {'summary': 'Report', 'transcripts': [{'page': page, 'text': 'Revenue: 12 USD'}],
            'observations': [{'page': page, 'entity': 'ACME', 'metric': 'Revenue', 'value': 12,
                              'unit': 'USD', 'period': '2025', 'population': '', 'denominator': None,
                              'source_quote': 'Revenue: 12 USD', 'extraction_kind': 'table', 'uncertainty': ''}]}


def fake_stream(monkeypatch, outputs):
    calls = []
    class Response:
        def __init__(self, value):
            self.value = value
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def raise_for_status(self):
            pass
        def iter_bytes(self):
            yield json.dumps({'choices': [{'message': {'content': json.dumps(self.value)}}]}).encode()
    def stream(*args, **kwargs):
        calls.append(kwargs)
        return Response(outputs[len(calls) - 1])
    monkeypatch.setattr(httpx, 'stream', stream)
    return calls


def test_image_inspection_and_preview():
    metadata = inspect_visual('scan.png', png())
    assert metadata['page_count'] == 1
    assert metadata['visual_capable'] is True
    assert render_visual_page('scan.png', png(), 1).startswith(b'\x89PNG')
    with pytest.raises(DemoError):
        render_visual_page('scan.png', png(), 0)


def test_transparent_image_uses_white_page_background():
    out = io.BytesIO()
    Image.new('RGBA', (16, 12), (0, 0, 0, 0)).save(out, format='PNG')
    preview = Image.open(io.BytesIO(render_visual_page('scan.png', out.getvalue(), 1)))
    assert preview.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize('pages', [[], [1, 1], [True], [2], list(range(1, 8))])
def test_page_selection_rejected_before_provider(pages):
    with pytest.raises(DemoError):
        extract_visual('scan.png', png(), pages, client())


def test_extract_unverified_typed_facts(monkeypatch):
    calls = fake_stream(monkeypatch, [result()])
    output = extract_visual('scan.png', png(), [1], client())
    assert output['observations'][0]['value'] == 12
    assert output['observations'][0]['verification_status'] == 'visual_unverified'
    assert output['review_status'] == 'needs_human_review'
    assert calls[0]['json']['model'] == 'gpt-4o'
    schema = calls[0]['json']['response_format']['json_schema']
    assert schema['strict'] is True
    assert 'transcripts' in schema['schema']['required']
    assert schema['schema']['properties']['transcripts']['items']['properties']['page']['enum'] == [1]
    assert calls[0]['json']['messages'][1]['content'][2]['image_url']['url'].startswith('data:image/png;base64,')


def test_invalid_page_repaired_once(monkeypatch):
    calls = fake_stream(monkeypatch, [result(2), result()])
    assert extract_visual('scan.png', png(), [1], client())['pages'] == [1]
    assert len(calls) == 2


def test_invalid_numeric_output_fails_after_bounded_repair(monkeypatch):
    invalid = result()
    invalid['observations'][0]['value'] = True
    calls = fake_stream(monkeypatch, [invalid, invalid])
    with pytest.raises(LLMError, match='after repair'):
        extract_visual('scan.png', png(), [1], client())
    assert len(calls) == 2


def test_pdf_page_provenance_and_encrypted_rejection():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    out = io.BytesIO()
    writer.write(out)
    assert inspect_visual('report.pdf', out.getvalue())['page_count'] == 2
    assert render_visual_page('report.pdf', out.getvalue(), 2).startswith(b'\x89PNG')
    writer.encrypt('password')
    encrypted = io.BytesIO()
    writer.write(encrypted)
    with pytest.raises(DemoError, match='Encrypted'):
        inspect_visual('report.pdf', encrypted.getvalue())


def test_oversized_or_invalid_image_rejected():
    with pytest.raises(DemoError, match='5 MiB'):
        inspect_visual('scan.png', b'x' * (5 * 1024 * 1024 + 1))
    with pytest.raises(DemoError, match='decode'):
        inspect_visual('scan.png', b'bad image')
