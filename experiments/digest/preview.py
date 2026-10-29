"""Render a static preview page (digest cards + folded evidence) from a digest experiment output dir.
Usage: python experiments/digest/preview.py OUT_DIR  -> OUT_DIR/preview.html  (open with ?t=dark for dark mode)"""
import html, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEC = [("what", "它是什么"), ("view", "你的核心看法"), ("evolution", "如何演变"), ("record", "对错记录")]
OUTC = {"confirmed": "已验证", "refuted": "被推翻", "mixed": "部分成立", "unknown": "未知"}
CSS = """
.dg{max-width:880px;margin:0 auto 48px}.dg-card{background:var(--surface);border:1px solid var(--line, var(--border));border-radius:14px;padding:28px 32px;box-shadow:0 1px 2px rgb(0 0 0/.06)}
.dg-kick{font-size:12px;letter-spacing:.08em;color:var(--accent);margin-bottom:8px}.dg h2{font-size:26px;margin-bottom:6px}
.dg-sec{margin-top:22px}.dg-sec h3{font:600 13px var(--sans, sans-serif);letter-spacing:.06em;color:var(--muted);margin-bottom:8px}
.dg-s{font:16px/1.85 var(--serif);margin:6px 0}.dg-s sup a{color:var(--accent);font:12px var(--sans, sans-serif);margin-left:2px;cursor:pointer}
.dg-st{display:inline-block;font:12px/1.8 var(--sans, sans-serif);border-radius:999px;padding:0 9px;margin-right:8px;background:var(--accent-soft, var(--accent-weak));color:var(--accent)}
.dg-ts{font:12px var(--sans, sans-serif);color:var(--muted);margin-right:8px;font-variant-numeric:tabular-nums}
.dg-fn{margin-top:20px;border-top:1px solid var(--border);padding-top:12px;font-size:12px;color:var(--muted)}.dg-fn li{margin:3px 0}.dg-fn q{color:var(--ink)}
details.dg-ev{margin-top:16px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 18px}details.dg-ev summary{font-size:13px;color:var(--muted)}
.dg-pt{display:grid;grid-template-columns:96px 1fr;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);font-size:14px}.dg-pt span{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
.dg-meta{font-size:12px;color:var(--muted);margin-top:4px}
"""


def card(kick, title, meta, res, pts):
    e = html.escape
    fns, body = [], []
    for key, label in SEC:
        rows = [s for s in res.get("sentences", []) if s.get("section") == key]
        if not rows:
            continue
        body.append(f'<div class="dg-sec"><h3>{label}</h3>')
        for s in rows:
            refs = []
            for ev in s["evidence"]:
                fns.append(ev); refs.append(f'<a title="{e(ev["quote"])}">[{len(fns)}]</a>')
            pre = (f'<span class="dg-st">{e(s["stance"])}</span>' if s.get("stance") else "") + \
                  (f'<span class="dg-ts">{e(s["ts"])}</span>' if s.get("ts") else "") + \
                  (f'<span class="dg-st">{OUTC.get(s["outcome"], "")}</span>' if s.get("outcome") else "")
            body.append(f'<p class="dg-s">{pre}{e(s["text"])}<sup>{"".join(refs)}</sup></p>')
        body.append("</div>")
    fn = "".join(f'<li>[{i + 1}] <q>{e(f["quote"])}</q> · <code>{e(f["doc_id"][:14])}</code></li>' for i, f in enumerate(fns))
    pl = "".join(f'<div class="dg-pt"><span>{e((p.get("ts") or "时间未知")[:16])}</span><div>{e(p["text"])}</div></div>' for p in pts)
    return (f'<section class="dg"><div class="dg-card"><div class="dg-kick">{e(kick)}</div><h2>{e(title)}</h2><div class="dg-meta">{e(meta)}</div>'
            f'{"".join(body)}<ol class="dg-fn" style="list-style:none;padding-left:0">{fn}</ol></div>'
            f'<details class="dg-ev"><summary>依据 {len(pts)} 条（原始片段，默认折叠）</summary>{pl}</details></section>')


def main(out):
    out = pathlib.Path(out)
    theme = (ROOT / "web" / "theme.css").read_text(encoding="utf-8")
    merged = json.loads((out / "A_merged.json").read_text(encoding="utf-8"))
    parts = []
    for p in sorted(out.glob("[BC]_*.json")):
        res = json.loads(p.read_text(encoding="utf-8")) or {}
        inp = json.loads((out / p.stem / "input.json").read_text(encoding="utf-8"))
        if inp["kind"] == "line":
            parts.append(card(f"判断线 · {inp.get('topic')}", inp["title"], f"由 {len(merged['merged'])} 条合并线之一 · {len(inp['points'])} 个点", res, inp["points"]))
        else:
            parts.append(card(f"实体 · {inp['type']}", inp["name"], f"{len(inp['statements'])} 条相关表态 · {len(inp['mentions'])} 处去重提及", res, inp["statements"]))
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>ATLAS 综述卡预览</title><style>{theme}{CSS}
body{{padding:40px 24px}}</style><script>var t=new URLSearchParams(location.search).get('t');if(t)document.documentElement.dataset.theme=t;</script></head>
<body><main style="max-width:960px;margin:0 auto;padding:0"><div class="eyebrow">小样本实验 · 静态预览</div><h1 style="margin-bottom:28px">归纳在上，片段做依据</h1>{''.join(parts)}</main></body></html>"""
    (out / "preview.html").write_text(page, encoding="utf-8")
    print(out / "preview.html")


if __name__ == "__main__":
    main(sys.argv[1])
