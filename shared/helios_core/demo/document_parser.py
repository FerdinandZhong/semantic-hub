"""Extract bounded, local document text with deterministic source citations."""
from __future__ import annotations

import hashlib
import io
from pathlib import PurePath
import zipfile

from .registry import DemoError

MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_TEXT_BYTES = 256 * 1024
MAX_CHUNKS = 128
MAX_CHUNK_CHARS = 2000
MAX_ZIP_BYTES = 32 * 1024 * 1024


def _split(text: str):
    """Split without dropping characters; prefer paragraph, line, then word boundaries."""
    while text:
        end = min(len(text), MAX_CHUNK_CHARS)
        if end < len(text):
            for separator in ('\n\n', '\n', ' '):
                boundary = text.rfind(separator, end // 2, end)
                if boundary >= 0:
                    end = boundary + len(separator)
                    break
        yield text[:end]
        text = text[end:]


def _docx_units(data: bytes):
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        raise DemoError('DOCX support requires python-docx. Install the demo requirements.') from None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2048 or sum(item.file_size for item in entries) > MAX_ZIP_BYTES:
                raise DemoError('DOCX archive expands beyond the safe limit. Export a smaller document.')
            if any(item.flag_bits & 1 or item.file_size > max(1, item.compress_size) * 100 for item in entries):
                raise DemoError('DOCX archive is encrypted or has unsafe compression. Export a plain DOCX document.')
            if 'word/document.xml' not in archive.namelist():
                raise DemoError('Invalid DOCX document. Export the file as DOCX again.')
        document = Document(io.BytesIO(data))
        paragraph_number = table_number = 0
        for element in document.element.body.iterchildren():
            kind = element.tag.rsplit('}', 1)[-1]
            if kind == 'p':
                paragraph_number += 1
                yield Paragraph(element, document).text, f'paragraph {paragraph_number}'
            elif kind == 'tbl':
                table_number += 1
                for row_number, row in enumerate(Table(element, document).rows, 1):
                    # Merged cells share XML elements. Include their content once per row.
                    seen = set()
                    cells = []
                    for cell in row.cells:
                        if cell._tc not in seen:
                            seen.add(cell._tc)
                            if cell.tables:
                                raise DemoError('Nested DOCX tables are unsupported. Export the document as UTF-8 text.')
                            cells.append(cell.text)
                    yield '\t'.join(cells), f'table {table_number}, row {row_number}'
    except DemoError:
        raise
    except Exception:
        raise DemoError('Cannot read this DOCX document. Export it as DOCX or UTF-8 text again.') from None


def _pdf_units(data: bytes, image_pages=None):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise DemoError('PDF support requires pypdf. Install the demo requirements.') from None
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DemoError('Encrypted PDFs are unsupported. Upload a decrypted PDF or UTF-8 text.')
        if len(reader.pages) > 512:
            raise DemoError('PDF exceeds the 512-page limit. Upload a smaller document.')
        for number, page in enumerate(reader.pages, 1):
            # Inspect decompressed stream sizes before text extraction where possible.
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > MAX_ZIP_BYTES:
                raise DemoError('PDF page expands beyond the safe limit. Export a smaller PDF.')
            text = page.extract_text() or ''
            if not text.strip():
                # A page containing an image but no text needs OCR. Blank pages are safe.
                resources = page.get('/Resources')
                resources = resources.get_object() if resources else {}
                xobjects = resources.get('/XObject')
                xobjects = xobjects.get_object() if xobjects else {}
                if any(obj.get_object().get('/Subtype') == '/Image' for obj in xobjects.values()):
                    if image_pages is not None:
                        # Callers that can transcribe pages visually collect them instead.
                        image_pages.append(number)
                        continue
                    raise DemoError('PDF contains scanned pages without text. Run OCR or upload UTF-8 text.')
            yield text, f'page {number}'
    except DemoError:
        raise
    except Exception:
        raise DemoError('Cannot read this PDF. Export a text PDF or UTF-8 text again.') from None


def parse_document(filename: str, data: bytes, image_pages: list[int] | None = None) -> list[dict[str, str]]:
    """Parse TXT, Markdown, text PDF, or DOCX without fetching document links.

    When ``image_pages`` is a list, image-only PDF pages are appended to it instead of raising.
    """
    if not isinstance(filename, str) or not isinstance(data, bytes):
        raise DemoError('Provide a document filename and bytes.')
    if len(data) > MAX_INPUT_BYTES:
        raise DemoError('Document exceeds the 5 MiB upload limit. Upload a smaller document.')
    suffix = PurePath(filename).suffix.lower()
    if suffix not in {'.txt', '.md', '.pdf', '.docx'}:
        raise DemoError('Unsupported document type. Upload TXT, MD, PDF, or DOCX.')
    if not data:
        raise DemoError('Document is empty. Upload a document containing text.')
    is_text = suffix in {'.txt', '.md'}
    if is_text:
        try:
            value = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise DemoError('Text must use UTF-8 encoding. Save the document as UTF-8.') from None
        if '\x00' in value:
            raise DemoError('Text contains binary data. Save the document as UTF-8 text.')
        units = [(value, '')]
    else:
        units = _pdf_units(data, image_pages) if suffix == '.pdf' else _docx_units(data)
    chunks = []
    total = 0
    for value, location in units:
        total += len(value.encode('utf-8'))
        if total > MAX_TEXT_BYTES:
            raise DemoError('Extracted text exceeds 256 KiB. Upload a smaller document.')
        line = 1
        for part in _split(value):
            end_line = line + part.count('\n') - int(part.endswith('\n'))
            source = f'lines {line}-{max(line, end_line)}' if is_text else location
            line += part.count('\n')
            if not part.strip():
                continue
            if len(chunks) >= MAX_CHUNKS:
                raise DemoError('Document exceeds 128 text chunks. Upload a smaller document.')
            identity = hashlib.sha256((source + '\x00' + str(len(chunks)) + '\x00' + part).encode('utf-8')).hexdigest()[:24]
            chunks.append({'id': f'chunk_{identity}', 'text': part, 'location': source})
    if not chunks and not image_pages:
        raise DemoError('Document has no extractable text. Run OCR for scanned PDFs or upload UTF-8 text.')
    return chunks
