"""Generic 'judgment line' lens: group statements into topic lines (one card per line),
ordered in time, with stance-change markers and user corrections.
Topics / keywords / stance words all come from the lens config."""
import re, json, os
from . import Lens

class JudgmentLinesLens(Lens):
    name = "judgment_lines"
    title = "判断线"
    def build(self, docs):
        c = self.config
        topics = {k: re.compile("|".join(map(re.escape, v)), re.I) for k, v in c["topics"].items()}
        judge = re.compile("|".join(map(re.escape, c.get("judgment_markers", []))) or r"(?!)")
        turn = re.compile("|".join(map(re.escape, c.get("turn_markers", []))) or r"(?!)")
        corr = self._corrections()
        lines = {k: [] for k in topics}
        for d in docs:
            if d.meta.get("sensitive"):
                continue
            for k, rx in topics.items():
                if rx.search(d.text) and judge.search(d.text):
                    lines[k].append({"id": d.id, "ts": d.ts, "text": d.text,
                                     "turn": bool(turn.search(d.text)),
                                     "correction": corr.get(d.id)})
        cards = []
        for k, items in lines.items():
            if len(items) < c.get("min_points", 2):
                continue
            items.sort(key=lambda x: x["ts"])
            cards.append({"topic": k, "first": items[0]["ts"], "last": items[-1]["ts"],
                          "n": len(items), "turns": sum(i["turn"] for i in items),
                          "points": items, "outcome": c.get("outcomes", {}).get(k)})
        cards.sort(key=lambda x: x["last"], reverse=True)
        return {"type": "judgment_lines", "method": "rules (lens config)", "cards": cards}

    def _corrections(self):
        # user feedback ('wrong' / 'note') lives in the PRIVATE data dir, not the repo
        p = os.path.join(self.ctx["data_dir"], "corrections.jsonl")
        out = {}
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.strip():
                    o = json.loads(line); out[o["doc_id"]] = o
        return out
