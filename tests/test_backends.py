import tempfile
import unittest
from pathlib import Path

from atlas.backends.base import Backend, ROUTES, char_span_ref, dispatch, validate_ref
from atlas.backends.atlas_sqlite import AtlasSqliteBackend
from atlas.backends.mrmem import MrMemBackend
from atlas.web_data import ReadModel
from examples.tasks_demo.seed_ui_v2 import seed


class BackendTests(unittest.TestCase):
    def test_all_routes_preserve_read_model_payloads_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp)
            before = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
            for sensitive in (False, True):
                backend = AtlasSqliteBackend(tmp, sensitive)
                self.assertIsInstance(backend, Backend)
                model = ReadModel(tmp, sensitive)
                for route in ROUTES:
                    params = {'id': 'fiction-garden', 'q': '虚构'}
                    if route == 'evidence':
                        params = {'id': 'fiction-s0', 'kind': 'statements'}
                    self.assertEqual(dispatch(backend, route, params), model.get(route, params))
                for route in ('line', 'entity', 'evidence', 'snapshot'):
                    with self.assertRaises(KeyError):
                        dispatch(backend, route, {'id': 'missing'})
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(tmp).iterdir()})

    def test_atlas_ref_is_additive_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp)
            backend = AtlasSqliteBackend(tmp)
            payload = backend.evidence({'kind': 'statements', 'id': 'fiction-s0'})
            self.assertEqual(payload['ref'], char_span_ref(payload['pointer']))
            self.assertEqual(payload['ref']['kind'], 'char_span')
            self.assertEqual(payload['pointer']['ref'], payload['ref'])
            self.assertEqual(payload['ref']['end'] - payload['ref']['start'], len(payload['quote']))
            ref = backend.entities({})['nodes'][0]['evidence'][0]['ref']
            self.assertEqual(validate_ref(ref), ref)

    def test_paragraph_ref_fake_and_unconnected_mrmem(self):
        class Fake(MrMemBackend):
            def evidence(self, params):
                return {'ref': validate_ref({'kind': 'message_paragraphs',
                         'record_id': 'fiction-message', 'paragraphs': [0, 2]})}
        self.assertIsInstance(Fake(), Backend)
        self.assertEqual(dispatch(Fake(), 'evidence', {})['ref']['paragraphs'], [0, 2])
        for route in ROUTES:
            with self.assertRaises(NotImplementedError):
                dispatch(MrMemBackend(), route, {})
        for ref in ({'kind': 'unknown'},
                    {'kind': 'message_paragraphs', 'record_id': 'fiction', 'paragraphs': []},
                    {'kind': 'message_paragraphs', 'record_id': 'fiction', 'paragraphs': [2, 0]},
                    {'kind': 'message_paragraphs', 'record_id': 'fiction', 'paragraphs': [True]},
                    {'kind': 'char_span', 'doc_id': 'fiction', 'start': 0, 'end': 0, 'quote_hash': 'a'*12}):
            with self.assertRaises(ValueError):
                validate_ref(ref)


    def test_server_dispatches_fake_paragraph_backend(self):
        import http.client
        import json
        import threading
        from atlas.server import create_server

        class Fake(MrMemBackend):
            def __init__(self, root, sensitive):
                self.sensitive = sensitive

            def evidence(self, params):
                return {'ref': validate_ref({'kind': 'message_paragraphs',
                         'record_id': 'fiction-message', 'paragraphs': [0]}),
                        'visible': self.sensitive}

        with tempfile.TemporaryDirectory() as tmp:
            seed(tmp)
            with create_server(tmp, port=0, backend_factory=Fake) as server:
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
                    try:
                        connection.request('GET', '/api/evidence?sensitive=1')
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                        payload = json.loads(response.read())
                        self.assertEqual(payload['ref']['kind'], 'message_paragraphs')
                        self.assertTrue(payload['visible'])
                    finally:
                        connection.close()
                finally:
                    server.shutdown()
                    thread.join()
