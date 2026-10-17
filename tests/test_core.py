from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
from organizer.extract import extract, extract_isolated, safe_name, DocumentError, MAX_UPLOAD
from organizer.metadata import suggest
from organizer.chunking import chunk_text
from organizer.service import Organizer
from organizer.store import Store


class FakeEmbedder:
    """Unit-test fixture only, not used for the recorded semantic evaluation."""
    available = True
    reason = ''
    dimension = 3
    calls = 0

    def encode(self, texts):
        self.calls += len(texts)
        result = []
        for t in texts:
            t = t.lower()
            v = np.array([1 + t.count('invoice') + t.count('payment'), 1 + t.count('engine') + t.count('car'), 1 + t.count('garden')], dtype=np.float32)
            result.append(v / np.linalg.norm(v))
        return np.array(result)


class ExtractionTests(unittest.TestCase):
    def test_text_and_markdown(self):
        self.assertEqual(extract('notes.txt', b'hello world')[0], 'hello world')
        self.assertEqual(extract('notes.md', b'# Heading\nSome text')[0], '# Heading\nSome text')

    def test_docx(self):
        # Minimal valid DOCX container fixture; no authoring dependency required.
        out = BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('[Content_Types].xml', '<Types/>')
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Invoice payment</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(extract('bill.docx', out.getvalue())[0], 'Invoice payment')

    def test_pdf(self):
        # A tiny text-bearing PDF built from explicit PDF objects, only for testing.
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
        stream = b'BT /F1 12 Tf 20 200 Td (Invoice payment received.) Tj ET'
        objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
        pdf=b'%PDF-1.4\n'; offsets=[0]
        for i,obj in enumerate(objects,1):
            offsets.append(len(pdf));pdf+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
        pos=len(pdf);pdf+=b'xref\n0 6\n0000000000 65535 f \n'
        for offset in offsets[1:]:pdf+=f'{offset:010} 00000 n \n'.encode()
        pdf+=b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(pos).encode()+b'\n%%EOF'
        self.assertIn('Invoice payment received.', extract('test.pdf',pdf)[0])

    def test_empty_malformed_oversize_and_names(self):
        for name,data in [('a.txt',b''),('a.txt',b'   '),('a.pdf',b'not pdf'),('a.docx',b'PKbroken'),('a.txt',b'\xff'),('a.txt',b'PK\x03\x04abc'),('a.txt',b'x'*(MAX_UPLOAD+1))]:
            with self.subTest(name=name), self.assertRaises(DocumentError):extract(name,data)
        for name in ('../../secret.txt','C:\\a.txt','/tmp/a.txt','a.exe','a\x00.txt','a\n.txt'):
            with self.assertRaises(DocumentError):safe_name(name)

    def test_isolated_parser(self):
        self.assertEqual(extract_isolated('a.txt',b'isolated test')[0],'isolated test')

    def test_docx_entity_and_zip_paths(self):
        for member,xml in [('word/document.xml','<!DOCTYPE x [<!ENTITY e "x">]><x/>'),('../word/document.xml','<x/>')]:
            f=BytesIO()
            with zipfile.ZipFile(f,'w') as z:
                z.writestr('[Content_Types].xml','<Types/>');z.writestr(member,xml)
            with self.assertRaises(DocumentError):extract('a.docx',f.getvalue())


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.embedder=FakeEmbedder();self.service=Organizer(Path(self.tmp.name),self.embedder)

    def tearDown(self):self.tmp.cleanup()

    def test_metadata_explainability(self):
        s=suggest('Invoice payment receipt. Payment was received for the invoice.','bill.txt')
        self.assertEqual(s['category'],'Finance');self.assertIn('invoice',s['classification_evidence'])
        self.assertTrue(0<=s['classification_strength']<=1);self.assertIn('invoice',s['keywords'])
        self.assertEqual(suggest('A quiet blue sky.','a.txt')['category'],'Other')

    def test_chunk_boundaries(self):
        text=' '.join(map(str,range(400)))
        c=chunk_text(text)
        self.assertEqual(c[0].split()[-32:],c[1].split()[:32])
        self.assertEqual(c[-1].split()[-1],'399')
        self.assertEqual(chunk_text(''),[])
        with self.assertRaises(ValueError):chunk_text(text,10,10)

    def test_index_cache_duplicate_persistence(self):
        a=self.service.ingest('bill.txt',b'Invoice payment receipt.')['document']
        calls=self.embedder.calls
        self.assertTrue(self.service.ingest('other.txt',b'Invoice payment receipt.')['duplicate'])
        self.assertEqual(self.embedder.calls,calls)
        self.service.reindex();self.assertEqual(self.embedder.calls,calls)
        fresh=Organizer(Path(self.tmp.name),self.embedder)
        self.assertEqual(fresh.store.get(a['id'])['filename'],'bill.txt')
        self.assertEqual(fresh.search('invoice','semantic')['results'][0]['id'],a['id'])

    def test_search_edit_trash_restore(self):
        a=self.service.ingest('invoice.txt',b'Invoice payment invoice payment.')['document']
        self.service.ingest('engine.txt',b'Engine engine car engine.')
        for mode in ('semantic','keyword','hybrid'):
            self.assertEqual(self.service.search('invoice',mode)['results'][0]['id'],a['id'])
        self.service.store.edit(a['id'],{'category':'Reviewed','title':'<script>alert(1)</script>','tags':['verified'],'collection':'School'})
        self.assertEqual(self.service.store.get(a['id'])['collection'],'School')
        self.assertEqual(len(self.service.search('',category='Reviewed')['results']),1)
        self.service.store.trash(a['id'],True)
        self.assertEqual(len(self.service.search('invoice','keyword')['results']),0)
        self.assertTrue(self.service.store.get(a['id'])['deleted'])
        self.assertEqual(len(self.service.store.list(deleted=True)),1)
        self.service.store.trash(a['id'],False)
        self.assertEqual(len(self.service.search('invoice','keyword')['results']),1)
        with self.assertRaises(ValueError):self.service.store.edit(a['id'],{'stored_name':'/etc/passwd'})

    def test_keyword_fallback(self):
        self.embedder.available=False;self.embedder.reason='Unavailable'
        self.service.ingest('note.txt',b'A garden grows vegetables.')
        result=self.service.search('garden','semantic')
        self.assertEqual(result['mode_used'],'keyword');self.assertEqual(len(result['results']),1)

    def test_rebuild_missing_vectors(self):
        self.embedder.available=False;self.embedder.reason='Unavailable'
        doc=self.service.ingest('pending.txt',b'Invoice payment pending.')['document']
        self.embedder.available=True
        result=self.service.search('invoice','semantic')
        self.assertEqual(result['results'],[])
        self.assertIn('lack embeddings',result['notice'])
        self.service.reindex()
        self.assertEqual(len(self.service.search('invoice','semantic')['results']),1)
        self.assertFalse(any('Keyword-only' in w for w in self.service.store.get(doc['id'])['warnings']))

    def test_filename_and_injection(self):
        self.service.ingest('special_name.txt',b'Ordinary content without a category.')
        self.assertEqual(len(self.service.search('special_name','keyword')['results']),1)
        self.assertEqual(self.service.search("' OR 1=1 --",'keyword')['results'],[])
