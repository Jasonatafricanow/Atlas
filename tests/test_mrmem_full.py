import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
import test_mrmem_reader as fixtures
from atlas.backends.mrmem_full import MrMemFull


class NativeProjectionTests(unittest.TestCase):
    write_memory=fixtures.ReaderTests.write_memory

    def setUp(self):
        fixtures.ReaderTests.setUp(self)
        self.reader=MrMemFull(self.root,'fiction-user')
        with closing(sqlite3.connect(self.root/'aml_source.sqlite')) as db:
            db.execute('ALTER TABLE messages ADD COLUMN seq INTEGER DEFAULT 1');db.commit()

    def test_scoped_source_version_and_history(self):
        source=self.reader.sources({})['items'][0]
        self.assertIsNone(source['ts'])
        self.assertEqual(self.reader.raw_evidence(dict(id='r',fingerprint=self.fp))['quote'],'虚构花圃')
        with self.assertRaises(KeyError): MrMemFull(self.root,'other').raw_evidence(dict(id='r',fingerprint=self.fp))
        self.assertEqual(self.reader.history({})['total'],1)
        self.assertEqual(self.reader.catalog({})['total'],1)

    def test_line_states_and_incomplete_evidence_preserve_projection(self):
        scope={k:None for k in ['agent_id','persona_id','relationship_id','world_id','interaction_id']}
        scope.update(domain='user',user_id='fiction-user')
        key=hashlib.sha256(json.dumps(scope,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        root=self.root/'lce_tree'/key;root.mkdir(parents=True)
        with closing(sqlite3.connect(root/'lines.sqlite')) as db:
            db.executescript('CREATE TABLE line_nodes(node_id,line_id,block_id); CREATE TABLE line_node_states(node_id,state_id,knowledge_at); CREATE TABLE line_node_memberships(node_id,retired_at); CREATE TABLE line_edges(line_id,parent_node_id,child_node_id,kind); CREATE TABLE line_edge_revisions(line_id,parent_node_id,child_node_id,retired_at);')
            db.execute("INSERT INTO line_nodes VALUES('n','line','block')")
            db.execute("INSERT INTO line_node_states VALUES('n','m','2024-01-01')")
            db.execute("INSERT INTO line_node_memberships VALUES('n',NULL)");db.commit()
        graph=self.reader.graph({})
        self.assertEqual(graph['lines'],['line'])
        self.assertTrue(graph['nodes'][0]['evidence_complete'])
        with closing(sqlite3.connect(self.root/'aml_source.sqlite')) as db:
            db.execute("UPDATE messages SET content='changed'");db.commit()
        graph=self.reader.graph({})
        self.assertEqual(len(graph['nodes']),1)
        self.assertFalse(graph['nodes'][0]['evidence_complete'])
        with self.assertRaises(ValueError):self.reader.raw_evidence(dict(id='r',fingerprint=self.fp))

    def test_preserved_date_precision_and_raw_search_pointer(self):
        with closing(sqlite3.connect(self.root/'aml_source.sqlite')) as db:
            db.execute('CREATE TABLE atlas_source_precision(record_id,source_date,precision,session_display_name,source_kind)')
            db.execute("INSERT INTO atlas_source_precision VALUES('r','2024-01-01','day','fictional session','legacy_quote_extract')");db.commit()
        self.assertEqual(self.reader.catalog({})['items'][0]['ts'],'2024-01-01')
        self.assertEqual(self.reader.sources({})['items'][0]['session_display_name'],'fictional session')
        self.assertEqual(self.reader.raw_evidence(dict(id='r',fingerprint=self.fp))['time_precision'],'day')
        class Service:
            def search(inner,user,query):return [dict(id='raw:r',content='fictional readout')]
        reader=MrMemFull(self.root,'fiction-user',Service())
        result=reader.search({'q':'fiction'})['items'][0]
        self.assertEqual(result['raw_source'],dict(id='r',fingerprint=self.fp))
        self.assertEqual(result['ts'],'2024-01-01')
