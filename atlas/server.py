"""Loopback-only, read-only UI server. Runtime data is never served as a file."""
import json
import sqlite3
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .backends.atlas_sqlite import AtlasSqliteBackend
from .backends.base import dispatch

WEB = Path(__file__).resolve().parent.parent / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # URLs can contain private search terms; never log requests.

    def reply(self, status, body, mime="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def error(self, code):
        self.reply(code, json.dumps({"error": code}).encode())

    def do_GET(self):
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.error(403)
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in allowed}:
            return self.error(403)
        url = urlsplit(self.path)
        try:
            if url.path.startswith("/api/"):
                params = {k: v[-1] for k, v in parse_qs(url.query).items()}
                if self.server.mrmem_user:
                    from .backends.mrmem_reader import MrMemReader
                    reader = MrMemReader(self.server.data_dir, self.server.mrmem_user)
                    route = url.path[5:]
                    methods = {"search": reader.search, "detail": reader.detail, "evidence": reader.evidence}
                    result = methods[route](params)
                    return self.reply(200, json.dumps(result, ensure_ascii=False).encode())
                backend = self.server.backend_factory(self.server.data_dir, params.get("sensitive") == "1")
                result = dispatch(backend, url.path[5:], params)
                return self.reply(200, json.dumps(result, ensure_ascii=False).encode())
            path = ("mrmem.html" if self.server.mrmem_user else "app.html") if url.path == "/" else url.path.lstrip("/")
            if path not in self.server.assets:
                return self.error(404)
            asset = WEB / path
            mime = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}[asset.suffix]
            self.reply(200, asset.read_bytes(), mime + "; charset=utf-8")
        except KeyError:
            self.error(404)
        except (ValueError, TypeError, IndexError):
            self.error(409)
        except (sqlite3.Error, OSError):
            self.error(503)

    def do_POST(self):
        self.error(405)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST


def create_server(data_dir, host="127.0.0.1", port=8765, *, backend_factory=AtlasSqliteBackend, digest_dir=None, mrmem_user=None):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("serve binds to loopback only")
    if mrmem_user:
        from .backends.mrmem_reader import MrMemReader
        MrMemReader(data_dir, mrmem_user)
        if digest_dir:
            raise ValueError("MR-Mem reader does not consume ATLAS digest files")
    elif not data_dir or not (Path(data_dir) / "graph.sqlite").is_file():
        raise ValueError("serve requires an existing graph.sqlite in an explicit data directory")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.data_dir = Path(data_dir).resolve()
    server.mrmem_user = mrmem_user
    server.backend_factory = partial(backend_factory, digest_dir=digest_dir) if digest_dir else backend_factory
    server.assets = {"app.html", "mrmem.html", "mrmem.css", "theme.css"} | {
        p.relative_to(WEB).as_posix() for p in (WEB / "js").rglob("*.js")
        if p.resolve().is_relative_to(WEB)}
    return server


def serve(data_dir, host="127.0.0.1", port=8765, *, digest_dir=None, mrmem_user=None):
    with create_server(data_dir, host, port, digest_dir=digest_dir, mrmem_user=mrmem_user) as server:
        print(f"ATLAS: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
