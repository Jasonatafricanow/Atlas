from contextlib import contextmanager
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from atlas.backends.mrmem_reader import MrMemReader


@contextmanager
def database(path):
    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fp = hashlib.sha256('虚构花圃'.encode()).hexdigest()
        with database(self.root / 'aml_source.sqlite') as db:
            db.executescript('CREATE TABLE messages(record_id,user_id,session_id,content,fingerprint,occurred_at,time_given,role);'
                             'CREATE TABLE threads(user_id,thread_id,summary,last_seq);'
                             'CREATE TABLE thread_members(user_id,thread_id,memory_id);')
            db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',
                       ('r','fiction-user','s','虚构花圃',self.fp,'2000-01-01',0,'user'))
        ref = dict(source_namespace='aml',session_id='s',record_id='r',fingerprint=self.fp)
        self.memory = dict(memory_id='m',scope=dict(domain='user',user_id='fiction-user'),
                           lifecycle='active',content='讨论虚构花圃',provenance=dict(source_refs=[ref]))
        self.write_memory()
        self.reader = MrMemReader(self.root, 'fiction-user')

    def write_memory(self):
        with database(self.root / 'memory.sqlite') as db:
            db.execute('CREATE TABLE IF NOT EXISTS canonical_memory(payload)')
            db.execute('DELETE FROM canonical_memory')
            db.execute('INSERT INTO canonical_memory VALUES(?)',(json.dumps(self.memory),))

    def test_search_detail_and_unknown_time(self):
        item = self.reader.search({'q':'花圃'})['items'][0]
        self.assertIsNone(item['ts'])
        self.assertNotIn('quote', item)
        self.assertEqual(self.reader.detail({'id':'m'})['segments'], [])
        self.assertEqual(self.reader.evidence(dict(id='m',index='0',fingerprint=self.fp))['quote'],'虚构花圃')

    def test_isolation_and_invalidation(self):
        self.assertEqual(MrMemReader(self.root,'another-user').search({})['items'],[])
        with self.assertRaises(KeyError):
            MrMemReader(self.root,'another-user').evidence(dict(id='m',index='0',fingerprint=self.fp))
        with database(self.root / 'aml_source.sqlite') as db:
            db.execute("UPDATE messages SET content='改变的虚构文本'")
        self.assertEqual(self.reader.search({})['items'],[])
        with self.assertRaises(ValueError):
            self.reader.evidence(dict(id='m',index='0',fingerprint=self.fp))

    def test_inactive_and_stale_selection(self):
        with self.assertRaises(ValueError):
            self.reader.evidence(dict(id='m',index='0',fingerprint='old'))
        self.memory['lifecycle'] = 'superseded'
        self.write_memory()
        self.assertEqual(self.reader.search({})['items'],[])

    def test_http_reader_without_atlas_graph_and_no_writes(self):
        import threading
        import urllib.request
        from atlas.server import create_server
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with create_server(self.root, port=0, mrmem_user='fiction-user') as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                for route in ('/', '/api/search?q=fiction', '/api/detail?id=m',
                              '/api/evidence?id=m&index=0&fingerprint='+self.fp):
                    with urllib.request.urlopen(base+route) as response:
                        self.assertEqual(response.status,200)
                with self.assertRaises(Exception):
                    urllib.request.urlopen(base+'/api/home')
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_segment_and_member_invalidation(self):
        with database(self.root / 'aml_source.sqlite') as db:
            db.execute('INSERT INTO threads VALUES(?,?,?,?)',('fiction-user','t','虚构成熟段',1))
            db.execute('INSERT INTO thread_members VALUES(?,?,?)',('fiction-user','t','m'))
        self.assertEqual(self.reader.detail({'id':'m'})['segments'][0]['summary'],'虚构成熟段')
        with database(self.root / 'aml_source.sqlite') as db:
            db.execute('INSERT INTO thread_members VALUES(?,?,?)',('fiction-user','t','missing'))
        self.assertEqual(self.reader.detail({'id':'m'})['segments'],[])

    def test_native_hits_map_without_literal_filter_or_reordering(self):
        class Service:
            def search(inner, user, query):
                self.assertEqual(user,'fiction-user')
                return [dict(id='line:m',content='native semantic result',score=0.7),
                        dict(id='raw:r',content='native raw result',score=0.2)]
        reader = MrMemReader(self.root,'fiction-user',Service())
        data = reader.search({'q':'not present in any local text'})
        self.assertEqual(data['search_mode'],'mrmem_runtime')
        self.assertEqual([i['memory_ids'] for i in data['items']],[['m'],['m']])
        self.assertEqual([i['score'] for i in data['items']],[0.7,0.2])
