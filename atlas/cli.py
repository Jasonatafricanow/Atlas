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
    from .graph.store import GraphStore
    from .profile import sync_corrections
    graph = GraphStore(cfg["data_dir"])
    try:
        sync_corrections(graph, cfg["data_dir"])
        snapshot = {table: [json.loads(row[0]) for row in graph.db.execute(
            f"SELECT data FROM {table} ORDER BY id")]
            for table in ("nodes", "edges", "propositions", "statements", "lines")}
    finally:
        graph.close()
    views = []
    for L in cfg.get("lenses", []):
        cls = R.load(L["lens"], R.BUILTIN_LENSES)
        lc = {}
        if L.get("config"):
            p = L["config"] if os.path.isabs(L["config"]) else os.path.join(cfg["config_dir"], L["config"])
            with open(p, encoding="utf-8") as stream:
                lc = json.load(stream)
        lens = cls(lc, {"data_dir": cfg["data_dir"], "graph": snapshot})
        views.append({"name": L.get("id", lens.name), "title": L.get("title", lens.title), "view": lens.build(docs)})
    out = cfg["out_dir"]; os.makedirs(out, exist_ok=True)
    data = {"atlas": __version__, "built": datetime.datetime.now().isoformat(timespec="seconds"),
            "n_docs": len(docs), **snapshot, "lenses": views}
    with open(os.path.join(out, "atlas.json"), "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
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
    for name in ("make", "list", "claim", "submit", "validate", "merge", "reap", "run"):
        parser = tasks.add_parser(name)
        parser.add_argument("--config")
        if name == "run":
            parser.add_argument("--runner", choices=["codex", "agy", "grok", "cmd"], required=True)
            parser.add_argument("--parallel", type=int, default=4)
            parser.add_argument("--print-cmd", action="store_true")
            parser.add_argument("--timeout", type=float, default=660)
        if name == "make":
            parser.add_argument("--kind", choices=["extract_entities", "resolve_entities", "gen_propositions", "cluster_lens"], required=True)
            parser.add_argument("--input", help="resolution input JSON with candidates, nodes and documents")
            parser.add_argument("--node", help="graph node for gen_propositions")
        if name == "list":
            parser.add_argument("--json", action="store_true")
        if name in ("claim", "submit", "validate", "merge"):
            parser.add_argument("task_id", nargs="?" if name == "merge" else None)
        if name == "merge":
            parser.add_argument("--all", action="store_true")
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
        options = cfg.get("tasks", {}) if cfg else {}
        queue = Queue(data_dir, store, options.get("forbidden_terms"), options.get("batch_docs", 50), options.get("batch_chars", 40000))
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
            if a.kind == "cluster_lens":
                from .tasks.lines import make_lines
                from .profile import sync_corrections
                if a.input or a.node:
                    raise ValueError("cluster_lens uses the persisted graph snapshot")
                graph = GraphStore(data_dir)
                try:
                    sync_corrections(graph, data_dir)
                    result = make_lines(queue, graph)
                finally:
                    graph.close()
            elif a.kind == "gen_propositions":
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
        elif a.action == "run":
            from .tasks.runners import run
            result = run(queue, a.runner, cfg or {}, a.parallel, a.print_cmd, a.timeout)
        elif a.action == "claim": result = queue.claim(a.task_id, a.owner, a.lease_seconds)
        elif a.action == "submit": result = queue.submit(a.task_id, a.file, a.owner)
        elif a.action == "validate": result = queue.validate(a.task_id)
        elif a.action == "merge":
            from .tasks.merge import merge
            graph = GraphStore(data_dir)
            try:
                if a.all == bool(a.task_id):
                    raise ValueError("provide one task_id or --all")
                result = ([merge(queue, graph, r["task_id"]) for r in queue.list() if r["state"] == "accepted"]
                          if a.all else merge(queue, graph, a.task_id))
            finally:
                graph.close()
        else: result = queue.reap()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        records = result if isinstance(result, list) else [result]
        return int(any(isinstance(r, dict) and r.get("state") == "rejected" for r in records))
    finally:
        store.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
