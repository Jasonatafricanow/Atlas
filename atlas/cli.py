"""atlas ingest|build|all --config <path>"""
import argparse, json, os, shutil, datetime
from . import config as C, registry as R, __version__
from .store import Store

HERE = os.path.dirname(os.path.abspath(__file__))

def ingest(cfg):
    st = Store(cfg["data_dir"])
    for src in cfg.get("sources", []):
        A = R.load(src["adapter"], R.BUILTIN_ADAPTERS)
        opts = dict(src.get("options", {}))
        if "path" in opts and not os.path.isabs(opts["path"]):
            opts["path"] = os.path.join(cfg["data_dir"], opts["path"])
        print(f"ingest {src['adapter']}: {st.upsert(A(**opts).read())} docs")
    return st

def build(cfg, st=None):
    st = st or Store(cfg["data_dir"])
    docs = list(st.all())
    views = []
    for L in cfg.get("lenses", []):
        cls = R.load(L["lens"], R.BUILTIN_LENSES)
        lc = {}
        if L.get("config"):
            p = L["config"] if os.path.isabs(L["config"]) else os.path.join(cfg["config_dir"], L["config"])
            lc = json.load(open(p, encoding="utf-8"))
        lens = cls(lc, {"data_dir": cfg["data_dir"]})
        views.append({"name": L.get("id", lens.name), "title": L.get("title", lens.title), "view": lens.build(docs)})
    out = cfg["out_dir"]; os.makedirs(out, exist_ok=True)
    data = {"atlas": __version__, "built": datetime.datetime.now().isoformat(timespec="seconds"),
            "n_docs": len(docs), "views": views}
    json.dump(data, open(os.path.join(out, "atlas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # data.js lets index.html work from file:// without fetch
    with open(os.path.join(out, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.ATLAS_DATA=" + json.dumps(data, ensure_ascii=False) + ";")
    shutil.copy(os.path.join(HERE, "..", "web", "index.html"), os.path.join(out, "index.html"))
    print(f"built {len(views)} views from {len(docs)} docs -> {out}")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas")
    ap.add_argument("cmd", choices=["ingest", "build", "all"])
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    cfg = C.load(a.config)
    R.add_paths([p if os.path.isabs(p) else os.path.join(cfg["config_dir"], p)
                 for p in cfg.get("plugins", {}).get("paths", [])])
    if a.cmd == "ingest": ingest(cfg)
    elif a.cmd == "build": build(cfg)
    else: build(cfg, ingest(cfg))

if __name__ == "__main__":
    main()
