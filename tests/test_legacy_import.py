import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('mr_mem_aml'),'paired MR-Mem source is optional')
class LegacyImportTests(unittest.TestCase):
    def test_preserves_session_grouping_and_date_precision_without_inventing_lines(self):
        from examples.import_legacy_archive import run
        from atlas.backends.mrmem_full import MrMemFull
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);previous='0'*64;quotes=[]
            for i,(chat,clock) in enumerate([('fictional garden',''),('fictional rain','10:20'),('fictional garden','')]):
                text=f'fictional garden record {i}'
                current=hashlib.sha256((previous+'|2024-01-01|'+chat+'|'+text).encode()).hexdigest()
                quotes.append(dict(id=i,q=text,date='2024-01-01',tm=clock,chat=chat,h=current,s=False));previous=current
            source=root/'archive.json'
            source.write_text(json.dumps(dict(meta={},quotes=quotes,ins=dict(cards=[dict(ids=[0,2],title='fictional insight',body='fictional projection')]))),encoding='utf-8')
            before=source.read_bytes()
            report=run(source,root/'native','fiction-user')
            self.assertEqual((report['raw_sources'],report['sessions'],report['preserved_projections']),(3,2,1))
            self.assertEqual(report['model_calls'],0)
            self.assertFalse((root/'native'/'lce_tree').exists())
            self.assertEqual(source.read_bytes(),before)
            reader=MrMemFull(root/'native','fiction-user')
            rows=reader.sources({})['items']
            self.assertEqual(rows[0]['session_id'],rows[2]['session_id'])
            self.assertNotEqual(rows[0]['session_id'],rows[1]['session_id'])
            self.assertEqual(rows[0]['ts'],'2024-01-01')
            self.assertEqual(rows[0]['time_precision'],'day')
            self.assertEqual(rows[1]['time_precision'],'minute')
            self.assertEqual(rows[0]['source_kind'],'legacy_quote_extract')
            self.assertEqual(reader.catalog({})['total'],1)
            with self.assertRaises(ValueError):run(source,root/'native','fiction-user')
