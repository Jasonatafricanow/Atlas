from collections import defaultdict
from . import Lens

class TimelineLens(Lens):
    name = "timeline"
    title = "时间线"
    def build(self, docs):
        by = defaultdict(list)
        for d in docs:
            by[d.ts[:7]].append({"id": d.id, "ts": d.ts, "text": d.text, "channel": d.channel})
        return {"type": "timeline", "months": [{"month": m, "items": by[m]} for m in sorted(by, reverse=True)]}
