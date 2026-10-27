import tempfile
import unittest

from atlas.graph.models import Proposition
from atlas.graph.store import GraphStore


class GraphTests(unittest.TestCase):
    def test_supersede_persists_and_logs(self):
        with tempfile.TemporaryDirectory() as root:
            store = GraphStore(root)
            old = Proposition("p1", "Synthetic claim", [], [], confidence=0.5)
            new = Proposition("p2", "Revised synthetic claim", [], [], confidence=0.8)
            self.assertEqual(store.put("propositions", old), "ADD")
            self.assertEqual(store.put("propositions", old), "NOOP")
            store.supersede("propositions", "p1", new, "2024-02-01")
            store.close()
            store = GraphStore(root)
            self.assertEqual(store.get("propositions", "p1")["superseded_by"], "p2")
            self.assertEqual(store.get("propositions", "p1")["valid_to"], "2024-02-01")
            self.assertEqual(store.stats()["propositions"], 2)
            self.assertEqual(store.stats()["ops_log"], 4)
            with self.assertRaises(ValueError):
                store.put("propositions", old)
            store.close()

    def test_supersede_rollback(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as root:
            store = GraphStore(root)
            store.put("propositions", Proposition("p1", "Synthetic claim", [], []))
            store.db.execute("CREATE TRIGGER fail_supersede BEFORE UPDATE ON propositions BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
            store.db.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                store.supersede("propositions", "p1", Proposition("p2", "New claim", [], []), "2024-02-01")
            self.assertIsNone(store.get("propositions", "p2"))
            self.assertEqual(store.get("propositions", "p1")["status"], "proposed")
            self.assertEqual(store.stats()["ops_log"], 1)
            store.close()
