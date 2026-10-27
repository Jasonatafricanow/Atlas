import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from atlas.schema import Document
from atlas.store import Store
from atlas.tasks.guard import redact, valid_identity, valid_luhn
from atlas.tasks.queue import Queue
from atlas.tasks.runners import _looks_mojibake, command, extract_json, resolve_program, run

ROOT = Path(__file__).resolve().parents[1]


class GuardTests(unittest.TestCase):
    def test_credentials_and_line_only_logs(self):
        samples = ['sk-' + 'a' * 24, 'ghp_' + 'b' * 24, 'xoxb-' + 'c' * 24,
                   'AKIA' + 'A' * 16, 'eyJabc.def.ghi', 'a1' * 32,
                   'Ab9/' * 12, 'password' + '=fiction', '\u5bc6\u7801\uff1a' + 'fiction',
                   '-----BEGIN PRIVATE KEY-----\nfiction\n-----END PRIVATE KEY-----']
        for sample in samples:
            with self.subTest(sample=samples.index(sample)):
                with self.assertLogs('atlas.tasks.guard', level='WARNING') as logs:
                    result = redact('safe\n' + sample + '\nsafe')
                self.assertNotIn(sample, result)
                self.assertIn('[CREDENTIAL]', result)
                self.assertTrue(all('credential removed at line ' in line for line in logs.output))
                self.assertTrue(result.startswith('safe\n'))
                self.assertTrue(result.endswith('\nsafe'))

    def test_checksums(self):
        card = '4' + '1' * 15
        self.assertTrue(valid_luhn(card))
        self.assertFalse(valid_luhn(card[:-1] + '2'))
        prefix = '000000' + '20000101' + '001'
        weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        identity = prefix + '10X98765432'[sum(int(c) * w for c, w in zip(prefix, weights)) % 11]
        self.assertTrue(valid_identity(identity))
        self.assertFalse(valid_identity(identity[:-1] + '9'))
        for value in (card, identity):
            self.assertEqual(redact(value), '[CREDENTIAL]')
        self.assertEqual(redact('ordinary health and bereavement text'), 'ordinary health and bereavement text')


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.queue = Queue(self.temp.name, self.store)
        self.store.upsert(Document(f'fiction-{i:03}', 'synthetic', '2024-01-01', 'Synthetic garden.') for i in range(151))
        self.ids = self.queue.make()
        self.fake = ['{python}', str(ROOT / 'examples/tasks_demo/fake_agent.py'), '--task-dir', '{task_dir}']

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_parallel_and_evidence(self):
        results = run(self.queue, 'cmd', {'runners': {'cmd': {'cmd': self.fake}}}, parallel=4)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r['state'] == 'accepted' for r in results))
        self.assertEqual(run(self.queue, 'cmd', {}), [])

    def test_templates_dry_run(self):
        path = self.queue.locate(self.queue.list()[0]['task_id'])[1]
        for name in ('codex', 'agy', 'grok'):
            commands = run(self.queue, name, {}, print_cmd=True)
            self.assertEqual(len(commands), 4)
            argv = commands[0]
            self.assertEqual(argv[0], name)
            if name == 'codex':
                self.assertEqual(argv[-1], '-')
                continue
            schema = argv[argv.index('--json-schema') + 1]
            if name == 'grok':
                self.assertEqual(json.loads(schema)['type'], 'object')
            else:
                self.assertEqual(Path(schema), path / 'output.schema.json')
        self.assertTrue(all(r['state'] == 'pending' for r in self.queue.list()))
        with self.assertRaises(ValueError):
            run(self.queue, 'cmd', {})

    def test_stdout(self):
        for name in ('agy', 'grok'):
            if name == 'grok':
                for record in self.queue.list():
                    path = self.queue.locate(record['task_id'])[1]
                    path.rename(self.queue.root / 'pending' / path.name)
            result = run(self.queue, name, {'runners': {name: {'cmd': self.fake + ['--stdout']}}})
            self.assertTrue(all(r['state'] == 'accepted' for r in result))

    def test_failure_modes(self):
        for index, mode in enumerate(('bad', 'fail', 'missing', 'sleep')):
            # Keep only one pending task per mode.
            target = self.ids[index]
            for record in self.queue.list():
                state, path = self.queue.locate(record['task_id'])
                if record['task_id'] != target and state == 'pending':
                    path.rename(self.queue.root / 'rejected' / path.name)
            state, path = self.queue.locate(target)
            if state != 'pending':
                path.rename(self.queue.root / 'pending' / path.name)
            results = run(self.queue, 'cmd', {'runners': {'cmd': {'cmd': self.fake + ['--mode', mode]}}}, timeout=0.2 if mode == 'sleep' else 10)
            self.assertEqual(results[0]['state'], 'rejected')
            self.assertTrue(results[0]['errors'])

    def test_filtered_source_keeps_evidence_consistent(self):
        self.store.upsert([Document('credential-fiction', 'synthetic', '2024-01-01',
                                   'password' + '=fiction\nSynthetic garden.', meta={'sensitive': True})])
        self.queue.make()
        result = run(self.queue, 'cmd', {'runners': {'cmd': {'cmd': self.fake}}})
        self.assertTrue(all(r['state'] == 'accepted' for r in result))
        doc = next(d for d in self.store.all() if d.id == 'credential-fiction')
        self.assertTrue(doc.meta['sensitive'])
        self.assertEqual(doc.text, '[CREDENTIAL]\nSynthetic garden.')


class ResolveTests(unittest.TestCase):
    def test_python_resolves_absolute(self):
        import sys
        argv = resolve_program(['python' if sys.platform == 'win32' else sys.executable, '-V'])
        self.assertTrue(Path(argv[0]).is_absolute())
        self.assertEqual(argv[-1], '-V')

    def test_cmd_shim_is_wrapped(self):
        import os, sys
        with tempfile.TemporaryDirectory() as d:
            name = 'atlasfake'
            shim = Path(d) / (name + ('.cmd' if os.name == 'nt' else ''))
            shim.write_text('@echo off\necho ok\n' if os.name == 'nt' else '#!/bin/sh\necho ok\n')
            shim.chmod(0o755)
            old = os.environ['PATH']
            os.environ['PATH'] = d + os.pathsep + old
            try:
                argv = resolve_program([name, 'x'])
            finally:
                os.environ['PATH'] = old
            if os.name == 'nt':
                self.assertEqual([argv[-2].lower(), argv[-1]], [str(shim).lower(), 'x'])
                self.assertIn('/c', argv)
            else:
                self.assertEqual(argv, [str(shim), 'x'])

    def test_missing_program(self):
        with self.assertRaises(FileNotFoundError):
            resolve_program(['definitely-not-an-atlas-runner', 'x'])

    def test_extract_json_wrappers(self):
        self.assertEqual(extract_json('{"entities": []}'), {'entities': []})
        self.assertEqual(extract_json('{"result": "{\\"entities\\": [1]}"}'), {'entities': [1]})
        self.assertEqual(extract_json('{"structured_output": {"entities": [2]}}'), {'entities': [2]})
        self.assertEqual(extract_json('{"structuredOutput": {"ops": []}, "text": "x", "usage": {}}'), {'ops': []})
        self.assertEqual(extract_json('{"response": "{\\"ops\\": [1]}", "status": "ok"}'), {'ops': [1]})
        self.assertEqual(extract_json('note\n{"entities": [3]}\n'), {'entities': [3]})

    def test_codex_prompt_on_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d); queue = Queue(d, store)
            store.upsert([Document('fiction-1', 'synthetic', '2024-01-01', 'Synthetic garden.')])
            queue.make()
            argv = run(queue, 'codex', {}, print_cmd=True)[0]
            self.assertEqual(argv[-1], '-')
            self.assertFalse(any('INSTRUCTIONS' in a or '\n' in a for a in argv))
            store.db.close()

    def test_remake_same_content_is_idempotent_and_changed_is_clear(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(d); queue = Queue(d, store)
            store.upsert([Document('fiction-1', 'synthetic', '2024-01-01', 'Synthetic garden.')])
            first = queue.make()
            self.assertEqual(queue.make(), first)
            self.assertEqual(len(queue.list()), 1)
            store.upsert([Document('fiction-1', 'synthetic', '2024-01-01', 'Changed garden.')])
            with self.assertRaises(ValueError) as ctx:
                queue.make()
            self.assertIn('fresh ATLAS_DATA_DIR', str(ctx.exception))
            store.db.close()


class MojibakeTests(unittest.TestCase):
    def test_detects_corrupted_text(self):
        self.assertTrue(_looks_mojibake('{"text": "????????"}'))
        self.assertTrue(_looks_mojibake('\ufffd'))
        self.assertFalse(_looks_mojibake('{"text": "\u4f5c\u8005? \u662f\u7684"}'))
