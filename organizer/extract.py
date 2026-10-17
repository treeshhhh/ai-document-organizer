"""Bounded extraction of untrusted uploads. No macros, links, or code executed."""
from io import BytesIO
from pathlib import PurePosixPath
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_UPLOAD = 8 * 1024 * 1024
MAX_TEXT = 80000
ALLOWED = {'.pdf', '.docx', '.txt', '.md'}


class DocumentError(ValueError):
    pass


def safe_name(name: str) -> str:
    if not name or len(name) > 200 or '/' in name or '\\' in name or '\x00' in name or name in ('.', '..'):
        raise DocumentError('Use a plain filename without directory paths (maximum 200 characters).')
    if any(ord(c) < 32 for c in name):
        raise DocumentError('Filename contains control characters.')
    if PurePosixPath(name).suffix.lower() not in ALLOWED:
        raise DocumentError('Supported file types: PDF, DOCX, TXT, Markdown.')
    return name


def extract(name: str, content: bytes) -> tuple[str, list[str]]:
    safe_name(name)
    if not content:
        raise DocumentError('The file is empty.')
    if len(content) > MAX_UPLOAD:
        raise DocumentError('Maximum upload size is 8 MiB.')
    suffix = PurePosixPath(name).suffix.lower()
    warnings = []
    try:
        if suffix == '.pdf':
            if not content.startswith(b'%PDF-'):
                raise DocumentError('The file does not contain a PDF signature.')
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise DocumentError('Encrypted PDFs are not supported. Upload an unencrypted copy.')
            if len(reader.pages) > 100:
                raise DocumentError('PDF limit: 100 pages.')
            parts, count = [], 0
            for page in reader.pages:
                # Limit uncompressed content streams before text interpretation.
                stream = page.get_contents()
                if stream is not None and len(stream.get_data()) > 4 * 1024 * 1024:
                    raise DocumentError('PDF page content is too complex.')
                part = page.extract_text() or ''
                parts.append(part); count += len(part)
                if count > MAX_TEXT:
                    warnings.append('Extracted text was truncated to 80,000 characters.'); break
            text = '\n\n'.join(parts)
        elif suffix == '.docx':
            if not content.startswith(b'PK'):
                raise DocumentError('The file does not contain a DOCX ZIP signature.')
            with zipfile.ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(i.file_size for i in entries) > 24 * 1024 * 1024:
                    raise DocumentError('DOCX expanded content exceeds the safe limit.')
                if any('..' in PurePosixPath(i.filename).parts or i.filename.startswith('/') for i in entries):
                    raise DocumentError('Unsafe DOCX member path.')
                if 'word/document.xml' not in archive.namelist() or '[Content_Types].xml' not in archive.namelist():
                    raise DocumentError('ZIP file is not a DOCX document.')
                raw = archive.read('word/document.xml')
                if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                    raise DocumentError('XML entities are not supported.')
                root = ET.fromstring(raw)
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                text = '\n'.join(''.join(p.itertext()) if not list(p.iter(ns + 't')) else ''.join(t.text or '' for t in p.iter(ns + 't')) for p in root.iter(ns + 'p'))
        else:
            if b'\x00' in content or content.startswith((b'%PDF-', b'PK\x03\x04')):
                raise DocumentError('Text file contains binary content; use its actual file extension.')
            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise DocumentError('Text files must use UTF-8 encoding.')
            if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
                raise DocumentError('Text file contains binary control characters.')
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError('Could not parse this document. It may be malformed or unsupported.') from exc
    text = text.replace('\x00', '').replace('\r\n', '\n').strip()
    if not text:
        raise DocumentError('No readable text found. Scanned/image-only PDFs require OCR, which is not included.')
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
        if not warnings:
            warnings.append('Extracted text was truncated to 80,000 characters.')
    return text, warnings


def extract_isolated(name: str, content: bytes) -> tuple[str, list[str]]:
    import json
    import subprocess
    import sys
    from pathlib import Path
    safe_name(name)
    if not content or len(content) > MAX_UPLOAD:
        raise DocumentError('File must contain 1 byte to 8 MiB.')
    try:
        result = subprocess.run([sys.executable, '-m', 'organizer.parse_worker', name], input=content,
                                capture_output=True, timeout=15, cwd=Path(__file__).resolve().parents[1])
    except subprocess.TimeoutExpired as exc:
        raise DocumentError('Document parsing exceeded 15 seconds.') from exc
    try:
        parsed = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise DocumentError('Document parser stopped; the file may exceed resource limits.')
    if result.returncode:
        raise DocumentError(parsed.get('error', 'Document parsing failed.'))
    return parsed['text'], parsed['warnings']
