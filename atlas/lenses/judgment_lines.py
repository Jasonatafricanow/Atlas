"""A topic view over stored propositions; never infer stance changes."""
from . import Lens


class JudgmentLinesLens(Lens):
    name = "judgment_lines"
    title = '判断线'

    def build(self, docs):
        graph = self.ctx["graph"]
        lines = []
        for node in graph["nodes"]:
            if node["type"] != "topic":
                continue
            points = [dict(statement_id=p["prop_id"],
                           ts=p.get("valid_from") or p.get("observed_at"), shift="none")
                      for p in graph["propositions"] if node["node_id"] in p["subject_node_ids"]]
            points.sort(key=lambda p: (p["ts"] or "", p["statement_id"]))
            if points:
                lines.append(dict(line_id=node["node_id"], topic_node_id=node["node_id"],
                                  title=node["name"], timeline=points))
        return dict(type="judgment_lines", lines=lines)
