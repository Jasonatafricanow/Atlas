"""Offline digest pipeline with invented TEST001 and a fictional sector."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory

from atlas.backends.atlas_sqlite import AtlasSqliteBackend
from atlas.graph.models import Node
from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store
from experiments.digest.preview import main as preview
from experiments.digest.run_digest import digest_check, point
from experiments.digest.validate import validate_merge

FIXTURE = Path(__file__).parent / "fixtures" / "digest_stock.json"


class Citations(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.targets = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs["href"])
        if tag == "li" and "id" in attrs:
            self.targets.append(attrs["id"])


def test_stock_sector_digest_pipeline():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with TemporaryDirectory() as tmp:
        data, outputs = Path(tmp) / "fiction-data", Path(tmp) / "fiction-digests"
        corpus, graph = Store(data), GraphStore(data)
        docs, statements = {}, {}
        # Reserved URL punctuation exercises the original-member route too.
        member = "fiction:TEST001/first+%?#"
        try:
            graph.put("nodes", Node("fiction-stock", "instrument", "TEST001"))
            graph.put("nodes", Node("fiction-sector", "topic", "虚构纸月板块"))
            for i, doc in enumerate(fixture["documents"]):
                docs[doc["id"]] = doc["text"]
                corpus.upsert([Document(**doc, source="fiction", author="虚构观察者",
                                        channel="虚构市场笔记", tags=[], meta={})])
                ref = dict(doc_id=doc["id"], span=[0,len(doc["text"])],
                           quote_hash=hashlib.sha256(doc["text"].encode()).hexdigest()[:12])
                sid = f"fiction-market-s{i}"
                statements[sid] = dict(statement_id=sid, text=doc["text"], ts=doc["ts"],
                                       about=["fiction-stock","fiction-sector"], evidence=[ref])
                graph.put("statements", statements[sid])
            graph.put("lines", dict(line_id=member, title="TEST001虚构观察线",
                      topic_node_id="fiction-sector", timeline=[dict(statement_id=sid) for sid in statements]))
        finally:
            corpus.db.close()
            graph.close()
        inputs = [point({"st":statements,"docs":docs}, sid) for sid in statements]
        merged = {"merged":[{"title":"TEST001虚构综述", "reason":"虚构板块观察", "member_line_ids":[member]}]}
        assert not validate_merge(merged, [member])
        assert not digest_check(docs, json.dumps([p["ts"] for p in inputs]))(fixture["digest"])
        jobs = {
            "A_merged.json": merged,
            "B_line1/input.json": {"kind":"line", "title":"TEST001虚构综述", "points":inputs},
            "B_line1.json":fixture["digest"],
            "C_entity1/input.json":{"kind":"entity", "name":"TEST001", "type":"instrument", "statements":inputs},
            "C_entity1.json":fixture["digest"],
        }
        for name, value in jobs.items():
            path = outputs / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        backend = AtlasSqliteBackend(data, digest_dir=outputs)
        for identifier in ("B_line1", member):
            digest = backend.line({"id":identifier})["digest"]
            assert digest["validation"] == {"valid":4,"total":4,"dropped":0}
            assert digest["sentences"][1]["stance"] == "看多"
            for sentence in digest["sentences"]:
                for evidence in sentence["evidence"]:
                    drawer = backend.evidence(dict(kind="digest_line", id=identifier, **evidence))
                    assert drawer["quote"] == evidence["quote"]
        assert backend.entity({"id":"fiction-stock"})["digest"]["validation"]["valid"] == 4
        assert len(backend.home({})["home_views"]) == 6
        # HTTP query encoding must round-trip literal slash/plus/percent/hash.
        import http.client
        import threading
        from urllib.parse import urlencode
        from atlas.server import create_server
        with create_server(data, port=0, digest_dir=outputs) as server:
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            client = http.client.HTTPConnection("127.0.0.1", server.server_port)
            try:
                client.request("GET", "/api/line?" + urlencode({"id":member}))
                response = client.getresponse()
                assert response.status == 200
                assert json.loads(response.read())["digest"]["source"]["id"] == member
            finally:
                client.close()
                server.shutdown()
                worker.join()
        preview(outputs)
        parser = Citations()
        parser.feed((outputs / "preview.html").read_text(encoding="utf-8"))
        assert len(parser.links) == 8
        assert len(set(parser.targets)) == 8
        assert all(link.endswith("-1") for link in parser.links)
        assert {link[1:] for link in parser.links} == set(parser.targets)


def test_preview_optional_metadata_and_empty_evidence():
    from experiments.digest.preview import card
    page = card("fiction", "fiction", "", {"sentences":[
        {"section":"what", "text":"Fictional observation", "evidence":None},
        {"section":"record", "text":"Unverified", "evidence":[]}]}, [])
    assert "Fictional observation" in page
    assert "Unverified" in page
    assert 'href="#' not in page
