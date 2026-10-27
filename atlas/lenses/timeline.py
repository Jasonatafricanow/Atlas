"""Chronological graph references without source excerpts."""
from . import Lens


class TimelineLens(Lens):
    name = "timeline"
    title = '时间线'

    def build(self, docs):
        items = [dict(statement_id=p["prop_id"], ts=p.get("valid_from") or p.get("observed_at"))
                 for p in self.ctx["graph"]["propositions"]]
        return dict(type="timeline", items=sorted(items, key=lambda p: (p["ts"] or "", p["statement_id"])))
