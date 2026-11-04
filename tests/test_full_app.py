import http.client
import threading
import hashlib
import json
import unittest
from pathlib import Path
import test_mrmem_reader as fixtures
from atlas.archive import Archive
from atlas.full_app import FullApp
from atlas.folio_store import FolioStore, digest
from atlas.backends.mrmem_full import MrMemFull


class FullTests(unittest.TestCase):
    write_memory = fixtures.ReaderTests.write_memory
    def setUp(self):
        fixtures.ReaderTests.setUp(self)
        self.archive=self.root/'archive.json'
        h=hashlib.sha256(('0'*64+'|2024-01-01|fiction|fictional garden').encode()).hexdigest()
        self.archive.write_text(json.dumps(dict(meta={},quotes=[dict(id=0,q='fictional garden',date='2024-01-01',chat='fiction',h=h,s=False)])),encoding='utf-8')

    def test_full_app_archive_and_native_capabilities(self):
        app=FullApp(self.archive,data_dir=self.root,user_id='fiction-user')
        self.assertTrue(app.get('archive/verify',{})['valid'])
        self.assertEqual(app.get('runtime/catalog',{})['total'],1)
        self.assertFalse(app.get('runtime/graph',{})['available'])
        self.assertTrue(app.get('runtime/capabilities',{})['storage'])
        with self.assertRaises(PermissionError): app.post('runtime/add',{})

    def test_mutations_scope_and_instance_flush_are_explicit(self):
        calls=[]
        class Service:
            def call(self,route,payload=None): calls.append((route,payload));return {'success':True}
        app=FullApp(self.archive,data_dir=self.root,user_id='fiction-user',service=Service(),runtime_writes=True)
        app.post('runtime/add',{'user_id':'other','request_id':'fixture','messages':[]})
        self.assertEqual(calls[0][1]['user_id'],'fiction-user')
        with self.assertRaises(ValueError): app.post('runtime/flush',{})
        app.post('runtime/flush',{'scope':'all_users'})
        self.assertEqual(calls[-1],('admin/flush',{}))

    def test_folio_originals_are_immutable_and_saves_use_cas(self):
        text='fictional sealed text'; sha=hashlib.sha256(text.encode()).hexdigest()
        chain=hashlib.sha256(('GENESIS\n'+sha+'\nfiction-page').encode()).hexdigest()
        doc={'entries':[{'id':'fiction-page','versions':[dict(text=text,sha256=sha)],'chain_prev':'GENESIS','chain':chain,'notes':[]}], 'trust':{'aiMayWrite':{'original':False}}}
        seed=self.root/'folio.json';seed.write_text(json.dumps(doc),encoding='utf-8')
        store=FolioStore(seed,self.root/'sidecar'); revision=digest(doc)
        changed=json.loads(json.dumps(doc));changed['entries'][0]['notes'].append({'text':'fictional note'})
        next_revision=store.save(changed,revision)
        self.assertNotEqual(next_revision,revision)
        self.assertEqual(json.loads(seed.read_text()),doc)
        with self.assertRaises(ValueError): store.save(changed,revision)
        changed['entries'][0]['versions'][0]['text']='forbidden replacement'
        with self.assertRaises(ValueError): store.save(changed,next_revision)

    def test_http_write_requires_local_origin_and_session_token(self):
        from atlas.server import create_server
        server=create_server(self.root,port=0,archive_file=self.archive)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def post(headers):
                client=http.client.HTTPConnection('127.0.0.1',server.server_port)
                try:
                    client.request('POST','/api/folio',body='{}',headers=headers)
                    response=client.getresponse();response.read();return response.status
                finally:client.close()
            origin=f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(post({}),403)
            self.assertEqual(post({'Origin':'https://example.invalid','X-Atlas-Token':server.full_app.token}),403)
            self.assertEqual(post({'Origin':origin,'X-Atlas-Token':'wrong'}),403)
            self.assertEqual(post({'Origin':origin,'X-Atlas-Token':server.full_app.token}),404)
        finally:server.shutdown();server.server_close();thread.join()
