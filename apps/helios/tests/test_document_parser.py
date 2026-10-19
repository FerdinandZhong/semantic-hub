"""Bounded extraction preserves source text and gives stable citations."""
import io
import zipfile

import pytest

from helios_core.demo.document_parser import parse_document, MAX_INPUT_BYTES, MAX_TEXT_BYTES
from helios_core.demo.registry import DemoError


def test_long_paragraph_has_full_coverage_and_stable_unique_ids():
    text = ('repeated words ' * 700) + '\nlast line\n'
    first = parse_document('notes.md', text.encode())
    assert first == parse_document('notes.md', text.encode())
    assert ''.join(chunk['text'] for chunk in first) == text
    assert all(len(chunk['text']) <= 2000 for chunk in first)
    assert len({chunk['id'] for chunk in first}) == len(first)
    assert first[0]['location'] == 'lines 1-1'
    assert first[-1]['location'].endswith('-2')


def test_line_citations_match_exact_source_ranges():
    text = '\n'.join(f'{number:04d} ' + 'x' * 90 for number in range(60))
    chunks = parse_document('notes.txt', text.encode())
    assert ''.join(chunk['text'] for chunk in chunks) == text
    for chunk in chunks:
        start, end = map(int, chunk['location'].removeprefix('lines ').split('-'))
        for line in chunk['text'].splitlines():
            assert start <= int(line[:4]) + 1 <= end


def test_docx_paragraph_and_table_rows():
    docx = pytest.importorskip('docx')
    document = docx.Document()
    document.add_paragraph('Before table')
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = 'Name'
    table.cell(0, 1).text = 'Value'
    table.cell(1, 0).text = 'Revenue'
    table.cell(1, 1).text = '42'
    document.add_paragraph('After table')
    buffer = io.BytesIO()
    document.save(buffer)
    chunks = parse_document('report.docx', buffer.getvalue())
    assert [c['text'] for c in chunks] == ['Before table', 'Name\tValue', 'Revenue\t42', 'After table']
    assert [c['location'] for c in chunks] == ['paragraph 1', 'table 1, row 1', 'table 1, row 2', 'paragraph 2']


def pdf_bytes(*texts, encrypted=False):
    """Build a PDF; a None text produces an image-only (scanned) page."""
    pypdf = pytest.importorskip('pypdf')
    from pypdf.generic import NameObject, DecodedStreamObject, DictionaryObject
    writer = pypdf.PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=300)
        if text is None:
            image = DecodedStreamObject()
            image.set_data(b'\xff')
            image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/Im1'): writer._add_object(image)})})
            continue
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 12 Tf 20 200 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('secret')
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_page_citations_and_encryption():
    chunks = parse_document('report.pdf', pdf_bytes('First page', 'Second page'))
    assert [c['text'].strip() for c in chunks] == ['First page', 'Second page']
    assert [c['location'] for c in chunks] == ['page 1', 'page 2']
    with pytest.raises(DemoError, match='Encrypted'):
        parse_document('secret.pdf', pdf_bytes('Secret', encrypted=True))


def test_scanned_pdf_pages_are_collected_only_when_requested():
    mixed = pdf_bytes('Text page', None)
    with pytest.raises(DemoError, match='scanned pages'):
        parse_document('mixed.pdf', mixed)
    pages = []
    chunks = parse_document('mixed.pdf', mixed, pages)
    assert [c['location'] for c in chunks] == ['page 1'] and pages == [2]
    pages = []
    assert parse_document('scan.pdf', pdf_bytes(None, None), pages) == [] and pages == [1, 2]


@pytest.mark.parametrize('name,data,message', [
    ('x.exe', b'hello', 'Unsupported'),
    ('x.txt', b'', 'empty'),
    ('x.txt', b'\xff', 'UTF-8'),
    ('x.txt', b'\x00abc', 'binary'),
    ('x.txt', b' \n', 'no extractable'),
    ('x.pdf', b'not a pdf', 'Cannot read'),
    ('x.docx', b'not a zip', 'Cannot read'),
    ('x.txt', b'x' * (MAX_INPUT_BYTES + 1), '5 MiB'),
    ('x.txt', b'x' * (MAX_TEXT_BYTES + 1), '256 KiB'),
    ('x.txt', ('a ' * 128001).encode(), '128 text chunks'),
])
def test_errors(name, data, message):
    with pytest.raises(DemoError, match=message):
        parse_document(name, data)


def test_docx_compression_bomb_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', 'x' * 500000)
    with pytest.raises(DemoError, match='unsafe compression'):
        parse_document('bomb.docx', buffer.getvalue())


def test_invalid_argument_types():
    with pytest.raises(DemoError, match='filename and bytes'):
        parse_document('x.txt', 'not bytes')


def test_scanned_pdf_requires_ocr():
    pypdf = pytest.importorskip('pypdf')
    from pypdf.generic import NameObject, DecodedStreamObject, DictionaryObject, NumberObject
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    image = DecodedStreamObject()
    image.set_data(b'\x00')
    image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'), NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1), NameObject('/ColorSpace'): NameObject('/DeviceGray'), NameObject('/BitsPerComponent'): NumberObject(8)})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/I1'): writer._add_object(image)})})
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(DemoError, match='Run OCR'):
        parse_document('scan.pdf', buffer.getvalue())


@pytest.mark.parametrize('module,suffix', [('pypdf', '.pdf'), ('docx', '.docx')])
def test_optional_dependencies_have_actionable_errors(monkeypatch, module, suffix):
    import builtins
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == module:
            raise ImportError('missing')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', missing)
    with pytest.raises(DemoError, match='Install the demo requirements'):
        parse_document('document' + suffix, b'content')
