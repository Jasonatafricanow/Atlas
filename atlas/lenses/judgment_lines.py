"""Project accepted judgments; group unclassified sources without inventing shifts."""
from . import Lens
from ..chat import time_key


def grouped_lines(graph):
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    sources = {s["statement_id"]: s for s in graph.get("statements", [])}
    for p in graph["propositions"]:
        sources[p["prop_id"]] = dict(p, statement_id=p["prop_id"], about=p["subject_node_ids"],
                                     ts=p.get("ts", p.get("valid_from")), speaker=p.get("speaker"))
    groups = []
    covered = set()
    for line in graph.get("lines", []):
        points = {}
        about = set()
        for point in line["timeline"]:
            source = sources.get(point["statement_id"])
            if not source:
                continue
            item = dict(point, ts=source.get("ts"), speaker=source.get("speaker"), text=source["text"],
                        about=source["about"], evidence=source.get("evidence", []),
                        sensitive=source.get("sensitive", False))
            # A subsequent correction invalidates a previously accepted outcome basis.
            support = [sources.get(i) for i in item.get("outcome_statement_ids", [])]
            if source.get("status") in ("rejected", "superseded") or source.get("suppressed_by") or any(not s or s.get("suppressed_by") or s.get("status") in ("rejected", "superseded") for s in support):
                item.update(outcome="unknown", outcome_reason="", outcome_statement_ids=[])
            item["sensitive"] |= any(s and s.get("sensitive", False) for s in support)
            points[point["statement_id"]] = item
            about.update(source["about"])
        if points:
            groups.append(dict(line, points=points, about=about))
            covered.update(points)
    # Hub nodes (people, or nodes about most statements, e.g. the owner) would chain
    # everything into one mega line; they never join groups.
    freq = {}
    for src in sources.values():
        for n in set(src.get("about", [])):
            freq[n] = freq.get(n, 0) + 1
    limit = max(3, 0.25 * len(sources))
    hubs = {n for n, c in freq.items() if c > limit or nodes.get(n, {}).get("type") == "person"}
    for group in groups:
        group["agent"] = True
    fallback = graph.get("statements", []) or list(sources.values())
    for source in fallback:
        identifier = source["statement_id"]
        if identifier in covered:
            continue
        point = dict(source, shift=None, reason="未评估变化", outcome="unknown", outcome_statement_ids=[], outcome_reason="")
        groups.append(dict(points={identifier: point}, about=set(source["about"]), agent=False))
    # Connected components, not one card per statement or per shared node.
    merged = []
    for group in groups:
        index = 0
        while index < len(merged):
            other = merged[index]
            if (not (group["agent"] and other["agent"])) and (group["about"] & other["about"]) - hubs:
                group["about"].update(other["about"])
                group["points"] = {**group["points"], **other["points"]}
                group["agent"] = group["agent"] or other["agent"]
                if "title" not in group and "title" in other:
                    group.update(title=other["title"], topic_node_id=other["topic_node_id"])
                merged.pop(index)
                index = 0
            else:
                index += 1
        merged.append(group)
    result = []
    for group in merged:
        about = sorted(group["about"])
        topic = group.get("topic_node_id") or next((i for i in about if nodes.get(i, {}).get("type") == "topic"), about[0])
        points = sorted(group["points"].values(), key=lambda p: (time_key(p.get("ts")), p["statement_id"]))
        for index, point in enumerate(points):
            if index and point.get("shift") == "first":
                point.update(shift=None, reason="跨批次连接，未评估变化")
        result.append(dict(line_id="topic:" + topic, topic_node_id=topic, about=about,
                           title=nodes.get(topic, {}).get("name", topic) if any(p.get("sensitive") for p in points) else group.get("title") or nodes.get(topic, {}).get("name", topic), timeline=points))
    return result


class JudgmentLinesLens(Lens):
    name = "judgment_lines"
    title = "判断线"

    def build(self, docs):
        return dict(type="judgment_lines", lines=grouped_lines(self.ctx["graph"]))
