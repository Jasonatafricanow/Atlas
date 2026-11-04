import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from atlas.backends.mrmem_search import MrMemSearch


class SearchTests(unittest.TestCase):
    def test_native_order_scope_auth_and_failure(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                received.append((self.path, self.headers.get('Authorization'),
                                 json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'data':[
                    {'id':'line:second', 'content':'semantic match', 'score':2},
                    {'id':'line:first', 'content':'lexical match', 'score':1}]}).encode())
        with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            client = MrMemSearch(f'http://127.0.0.1:{server.server_port}', 'FICTION_SERVICE_TOKEN')
            try:
                with patch.dict(os.environ, {'FICTION_SERVICE_TOKEN':'fiction-auth'}):
                    result = client.search('fiction-user','different wording')
                self.assertEqual([r['id'] for r in result],['line:second','line:first'])
                self.assertEqual(received,[('/search','Bearer fiction-auth',
                    {'user_id':'fiction-user','query':'different wording','top_k':100})])
            finally:
                server.shutdown()
                thread.join()
        with self.assertRaises(OSError):
            MrMemSearch(client.url.removesuffix('/search')).search('fiction-user','query')

    def test_only_local_services(self):
        for url in ('https://example.com','http://127.0.0.1' + chr(64) + 'other.test',
                    'http://localhost/search','http://localhost?token=x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MrMemSearch(url)
