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
    commands = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ingest", "build", "all"):
        commands.add_parser(name).add_argument("--config", required=True)
    tasks = commands.add_parser("tasks").add_subparsers(dest="action", required=True)
    for name in ("make", "list", "claim", "submit", "validate", "merge", "reap"):
        parser = tasks.add_parser(name)
        parser.add_argument("--config")
        if name == "make":
            parser.add_argument("--kind", choices=["extract_entities", "resolve_entities", "gen_propositions"], required=True)
            parser.add_argument("--input", help="resolution input JSON with candidates, nodes and documents")
            parser.add_argument("--node", help="graph node for gen_propositions")
        if name == "list":
            parser.add_argument("--json", action="store_true")
        if name in ("claim", "submit", "validate", "merge"):
            parser.add_argument("task_id")
        if name == "claim":
            parser.add_argument("--owner", required=True)
            parser.add_argument("--lease-seconds", type=int, default=300)
        if name == "submit":
            parser.add_argument("--file", required=True)
            parser.add_argument("--owner")
    graph = commands.add_parser("graph").add_subparsers(dest="action", required=True)
    graph.add_parser("stats").add_argument("--config")
    profile = commands.add_parser("profile").add_subparsers(dest="action", required=True)
    for name in ("list", "correct"):
        parser = profile.add_parser(name)
        parser.add_argument("--config")
        if name == "correct":
            parser.add_argument("prop_id")
            parser.add_argument("--verdict", choices=["wrong", "right", "amend"], required=True)
            parser.add_argument("--note", default="")
    a = ap.parse_args(argv)
    try:
        if a.cmd in ("tasks", "graph", "profile"):
            return task_command(a)
        cfg = C.load(a.config)
        R.add_paths([p if os.path.isabs(p) else os.path.join(cfg["config_dir"], p)
                     for p in cfg.get("plugins", {}).get("paths", [])])
        if a.cmd == "ingest": ingest(cfg)
        elif a.cmd == "build": build(cfg)
        else: build(cfg, ingest(cfg))
        return 0
    except (C.ConfigError, ValueError, OSError) as exc:
        ap.error(str(exc))


def task_command(a):
    from .graph.store import GraphStore
    from .tasks.queue import Queue

    cfg = C.load(a.config) if a.config else None
    data_dir = cfg["data_dir"] if cfg else os.environ.get("ATLAS_DATA_DIR")
    if not data_dir:
        raise C.ConfigError("set ATLAS_DATA_DIR or provide --config; no default data path")
    if a.cmd == "graph":
        graph = GraphStore(data_dir)
        try:
            print(json.dumps(graph.stats(), indent=2))
        finally:
            graph.close()
        return 0
    if a.action == "make" and cfg:
        R.add_paths([p if os.path.isabs(p) else os.path.join(cfg["config_dir"], p)
                     for p in cfg.get("plugins", {}).get("paths", [])])
        store = ingest(cfg)
    else:
        store = Store(data_dir)
    try:
        queue = Queue(data_dir, store, cfg.get("tasks", {}).get("forbidden_terms") if cfg else None)
        if a.cmd == "profile":
            from .profile import correct, propositions, sync_corrections
            graph = GraphStore(data_dir)
            try:
                with queue.locked():
                    sync_corrections(graph, data_dir)
                    result = (propositions(graph) if a.action == "list" else
                              correct(graph, data_dir, a.prop_id, a.verdict, a.note))
            finally:
                graph.close()
        elif a.action == "make":
            from .tasks.queue import read_json
            from pathlib import Path
            if a.kind == "gen_propositions":
                from .profile import snapshot
                if not a.node or a.input:
                    raise ValueError("gen_propositions requires --node and uses the live graph snapshot")
                graph = GraphStore(data_dir)
                try:
                    payload = snapshot(graph, store, data_dir, a.node)
                finally:
                    graph.close()
                result = queue.make(a.kind, payload)
            else:
                result = queue.make(a.kind, read_json(Path(a.input)) if a.input else None)
        elif a.action == "list": result = queue.list()
        elif a.action == "claim": result = queue.claim(a.task_id, a.owner, a.lease_seconds)
        elif a.action == "submit": result = queue.submit(a.task_id, a.file, a.owner)
        elif a.action == "validate": result = queue.validate(a.task_id)
        elif a.action == "merge":
            from .tasks.merge import merge
            graph = GraphStore(data_dir)
            try:
                result = merge(queue, graph, a.task_id)
            finally:
                graph.close()
        else: result = queue.reap()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if isinstance(result, dict) and result.get("state") == "rejected" else 0
    finally:
        store.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
