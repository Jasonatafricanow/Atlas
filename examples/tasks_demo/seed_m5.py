"""Seed only the fixed, disposable M5 demo directory from fictional examples."""
import hashlib
import json
from pathlib import Path

from atlas.graph.models import Edge, Node, Proposition
from atlas.graph.store import GraphStore


def seed(data_dir):
    docs = [json.loads(line) for line in Path('examples/synthetic_corpus/reading_notes.jsonl').read_text(encoding='utf-8').splitlines()]
    evidence = [dict(doc_id=d['id'], span=[0, len(d['text'])],
                     quote_hash=hashlib.sha256(d['text'].encode()).hexdigest()[:12]) for d in docs[:2]]
    graph = GraphStore(data_dir)
    try:
        graph.put('nodes', Node('demo-topic', 'topic', 'Synthetic street activity', evidence, observed_at='2024-02-14'))
        graph.put('nodes', Node('demo-concept', 'concept', 'Synthetic mixed use', evidence))
        graph.put('nodes', Node('demo-sensitive', 'topic', 'Synthetic private topic', evidence, sensitive=True))
        graph.put('edges', Edge('demo-edge', 'demo-topic', 'demo-concept', 'related_to', evidence,
                                valid_from='2024-01-08', observed_at='2024-02-14'))
        graph.put('edges', Edge('demo-hidden-edge', 'demo-topic', 'demo-sensitive', 'related_to', evidence))
        graph.put('propositions', Proposition('demo-prop', 'Synthetic streets may benefit from mixed use.',
                  ['demo-topic'], evidence, confidence=0.65, valid_from='2024-02-14', observed_at='2024-02-14'))
        graph.put('propositions', Proposition('demo-private-prop', 'Synthetic private statement.',
                  ['demo-sensitive'], evidence, confidence=0.5, sensitive=True))
    finally:
        graph.close()


if __name__ == '__main__':
    seed(Path('_demo_out/m5-data'))
