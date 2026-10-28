"""Fictional UI fixture. Pass an explicit disposable destination."""
import argparse
import hashlib
from pathlib import Path

from atlas.graph.models import Edge, Node, Proposition
from atlas.graph.store import GraphStore
from atlas.schema import Document
from atlas.store import Store


def seed(root):
    root = Path(root)
    corpus = Store(root)
    texts = ["虚构记录：先在小花圃试种。", "虚构记录：试种成活，扩大到第二块花圃。", "虚构记录：雨水过多，暂停扩种。"]
    refs = []
    for index, text in enumerate(texts):
        identifier = f"fiction-doc-{index}"
        corpus.upsert([Document(id=identifier, source="fiction", ts=f"2025-0{index+1}-12", text=text,
                                author="虚构园丁", channel="虚构园艺笔记", tags=[], meta={})])
        refs.append(dict(doc_id=identifier, span=[0, len(text)], quote_hash=hashlib.sha256(text.encode()).hexdigest()[:12]))
    corpus.db.close()
    graph = GraphStore(root)
    try:
        graph.put("nodes", Node("fiction-garden", "topic", "花圃的试种与扩种", refs[:1]))
        graph.put("nodes", Node("fiction-rain", "concept", "雨水与土壤", refs[2:]))
        graph.put("nodes", Node("fiction-hidden", "topic", "虚构敏感主题", sensitive=True))
        graph.put("aliases", dict(alias_id="fiction-alias", node_id="fiction-garden", name="虚构试种"))
        graph.put("edges", Edge("fiction-edge", "fiction-rain", "fiction-garden", "related_to", refs[2:], valid_from="2025-03-12"))
        for index, text in enumerate(texts):
            graph.put("statements", dict(statement_id=f"fiction-s{index}", text=text, about=["fiction-garden"],
                      kind="opinion", stance=["试种", "扩种", "暂缓"][index], ts=f"2025-0{index+1}-12",
                      speaker="虚构园丁", evidence=[refs[index]], confidence=0.55, sensitive=False))
        graph.put("propositions", Proposition("fiction-prop", "虚构园丁倾向于先试种，再扩大规模。",
                  ["fiction-garden"], refs[:2], confidence=0.7, kind="preference"))
        for batch, indices in enumerate(((0, 1), (2,))):
            points = [dict(statement_id=f"fiction-s{i}", shift=["first", "strengthen", "reverse"][i],
                           reason=["首次记录", "试种结果支持扩大范围", "雨水条件改变了计划"][i],
                           outcome="confirmed" if i == 0 else "unknown",
                           outcome_reason="后续记录报告试种成活" if i == 0 else "",
                           outcome_statement_ids=["fiction-s1"] if i == 0 else []) for i in indices]
            graph.put("lines", dict(line_id=f"fiction-line-{batch}", title="虚构花圃计划",
                      topic_node_id="fiction-garden", timeline=points, sensitive=False))
    finally:
        graph.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    seed(parser.parse_args().data_dir)
