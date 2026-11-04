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
        style_policy = "style-src 'self' 'unsafe-inline'" if self.server.full_app else "style-src 'self'"
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; " + style_policy + "; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
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
                if self.server.full_app:
                    result=self.server.full_app.get(url.path[5:],params)
                    return self.reply(200,json.dumps(result,ensure_ascii=False).encode())
                if self.server.mrmem_user:
                    from .backends.mrmem_reader import MrMemReader
                    reader = MrMemReader(self.server.data_dir, self.server.mrmem_user, self.server.mrmem_search)
                    route = url.path[5:]
                    methods = {"search": reader.search, "detail": reader.detail, "evidence": reader.evidence, "toc": reader.overview, "home": reader.overview, "lines": reader.overview, "line": reader.detail, "entities": reader.unavailable, "entity": reader.unavailable}
                    result = methods[route](params)
                    return self.reply(200, json.dumps(result, ensure_ascii=False).encode())
                backend = self.server.backend_factory(self.server.data_dir, params.get("sensitive") == "1")
                result = dispatch(backend, url.path[5:], params)
                return self.reply(200, json.dumps(result, ensure_ascii=False).encode())
            path = ("original.html" if self.server.full_app else "app.html") if url.path == "/" else url.path.lstrip("/")
            if path not in self.server.assets:
                return self.error(404)
            asset = WEB / path
            mime = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}[asset.suffix]
            self.reply(200, asset.read_bytes(), mime + "; charset=utf-8")
        except KeyError:
            self.error(404)
        except (ValueError, TypeError, IndexError):
            self.error(409)
        except PermissionError:
            self.error(403)
        except (sqlite3.Error, OSError):
            self.error(503)

    def do_POST(self):
        full=self.server.full_app
        allowed={f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}
        if not full: return self.error(405)
        if (self.headers.get('Origin') not in allowed or
                self.headers.get('X-Atlas-Token')!=full.token or
                self.headers.get('Sec-Fetch-Site')=='cross-site'):
            return self.error(403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16*1024*1024: return self.error(413)
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): return self.error(400)
            result=full.post(urlsplit(self.path).path.removeprefix('/api/'),body)
            return self.reply(200,json.dumps(result,ensure_ascii=False).encode())
        except PermissionError: self.error(403)
        except KeyError: self.error(404)
        except (ValueError,TypeError,IndexError): self.error(409)
        except (OSError,sqlite3.Error): self.error(503)


    def reject_write(self): self.error(405)
    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = reject_write


def create_server(data_dir, host="127.0.0.1", port=8765, *, backend_factory=AtlasSqliteBackend, digest_dir=None, mrmem_user=None, mrmem_url=None, mrmem_token_env=None, archive_file=None, folio_file=None, state_dir=None, runtime_writes=False):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("serve binds to loopback only")
    if archive_file:
        if not Path(archive_file).is_file(): raise ValueError("archive file unavailable")
    elif mrmem_user:
        from .backends.mrmem_reader import MrMemReader
        MrMemReader(data_dir, mrmem_user)
        if digest_dir:
            raise ValueError("MR-Mem reader does not consume ATLAS digest files")
    elif not data_dir or not (Path(data_dir) / "graph.sqlite").is_file():
        raise ValueError("serve requires an existing graph.sqlite in an explicit data directory")
    from .backends.mrmem_search import MrMemSearch
    search_service = MrMemSearch(mrmem_url, mrmem_token_env) if mrmem_url else None
    full=None
    if archive_file:
        from .full_app import FullApp
        full=FullApp(archive_file,data_dir=data_dir,user_id=mrmem_user,service=search_service,
                     folio_file=folio_file,state_dir=state_dir,runtime_writes=runtime_writes)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.data_dir = Path(data_dir).resolve()
    server.full_app=full
    server.mrmem_user = mrmem_user
    server.mrmem_search = search_service
    server.backend_factory = partial(backend_factory, digest_dir=digest_dir) if digest_dir else backend_factory
    server.assets = {"app.html", "mrmem.html", "mrmem.css", "theme.css", "original.html", "original.css", "folio.html", "folio.css"} | {
        p.relative_to(WEB).as_posix() for p in (WEB / "js").rglob("*.js")
        if p.resolve().is_relative_to(WEB)}
    return server


def serve(data_dir, host="127.0.0.1", port=8765, *, digest_dir=None, mrmem_user=None, mrmem_url=None, mrmem_token_env=None, archive_file=None, folio_file=None, state_dir=None, runtime_writes=False):
    with create_server(data_dir, host, port, digest_dir=digest_dir, mrmem_user=mrmem_user, mrmem_url=mrmem_url, mrmem_token_env=mrmem_token_env, archive_file=archive_file, folio_file=folio_file, state_dir=state_dir, runtime_writes=runtime_writes) as server:
        print(f"ATLAS: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
