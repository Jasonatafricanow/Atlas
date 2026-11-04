import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from atlas.archive import Archive


class ArchiveTests(unittest.TestCase):
    def test_projection_preserves_ids_without_exposing_hidden_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'archive.json'; previous='0'*64; rows=[]
            for i,text in enumerate(['fictional garden','fictional sensitive note']):
                digest=hashlib.sha256((previous+'|2024-01-01|fiction|'+text).encode()).hexdigest()
                rows.append(dict(id=i,q=text,date='2024-01-01',chat='fiction',s=bool(i),h=digest))
                previous=digest
            path.write_text(json.dumps(dict(meta={},quotes=rows)),encoding='utf-8')
            archive=Archive(path)
            self.assertTrue(archive.verify()['valid'])
            self.assertEqual(archive.projection()['quotes'][1]['q'],'')
            self.assertEqual(archive.projection()['quotes'][1]['id'],1)
            with self.assertRaises(KeyError): archive.evidence(1)
            self.assertEqual(archive.evidence(1,True)['quote'],'fictional sensitive note')
            rows[0]['q']='changed'
            path.write_text(json.dumps(dict(meta={},quotes=rows)),encoding='utf-8')
            self.assertFalse(archive.verify()['valid'])
            with self.assertRaises(ValueError): archive.evidence(0)
