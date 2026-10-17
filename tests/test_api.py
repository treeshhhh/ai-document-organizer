from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app import create_app
from organizer.service import Organizer
from test_core import FakeEmbedder


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();service=Organizer(Path(self.tmp.name),FakeEmbedder())
        self.client=TestClient(create_app(organizer=service));self.client.__enter__()

    def tearDown(self):self.client.__exit__(None,None,None);self.tmp.cleanup()

    def upload(self,name='bill.txt',data=b'Invoice payment receipt.'):
        return self.client.post('/api/upload',files={'file':(name,data)})

    def test_end_to_end_upload_preview_edit_export_trash(self):
        r=self.upload();self.assertEqual(r.status_code,200,r.text);identity=r.json()['document']['id']
        self.assertEqual(self.client.get('/api/documents',params={'q':'invoice','mode':'keyword'}).json()['results'][0]['id'],identity)
        self.assertIn('Invoice',self.client.get('/api/documents/'+identity).json()['text'])
        r=self.client.patch('/api/documents/'+identity,json={'collection':'Work','tags':['paid']});self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/export').json()['documents'][0]['collection'],'Work')
        self.assertEqual(self.client.get('/api/documents/'+identity+'/original').content,b'Invoice payment receipt.')
        self.client.delete('/api/documents/'+identity);self.assertEqual(len(self.client.get('/api/documents').json()['results']),0)
        self.client.post('/api/documents/'+identity+'/restore');self.assertEqual(len(self.client.get('/api/documents').json()['results']),1)

    def test_validation_and_paths(self):
        for name,data in [('../secret.txt',b'x'),('x.pdf',b'notpdf'),('x.txt',b''),('x.exe',b'abc')]:
            self.assertEqual(self.upload(name,data).status_code,400)
        self.assertEqual(self.client.get('/api/documents/missing').status_code,404)
        self.assertEqual(self.client.get('/assets/secret.txt').status_code,404)
        self.assertEqual(self.client.get('/api/status',headers={'Origin':'http://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/status',headers={'Host':'evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/upload',content=b'x',headers={'Content-Length':'99999999'}).status_code,413)
        self.assertEqual(self.client.patch('/api/documents/unknown',content='notjson').status_code,400)

    def test_static_and_reindex(self):
        for route in ('/','/assets/app.js','/assets/style.css'):
            self.assertEqual(self.client.get(route).status_code,200)
        self.upload();self.assertEqual(self.client.post('/api/reindex',content=b'').status_code,200)
