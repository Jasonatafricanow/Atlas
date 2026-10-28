import contextlib
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from atlas.graph.store import GraphStore
from atlas.web_data import ReadModel
from atlas.web_derive import derive_home, derive_line, derive_pending, session_name
from examples.tasks_demo.seed_ui_v2 import seed


def point(identifier, ts=None, stance=None, outcomes=('unknown',), shift='first', **fields):
    return {'statement_id': identifier, 'source': dict(ts=ts, stance=stance, **fields),
            'annotations': [{'outcome': o, 'shift': shift} for o in outcomes]}


class DerivationTests(unittest.TestCase):
    def test_latest_dated_stance_and_span_preserve_source_times(self):
        points = [point('a', '2024-11-08T16:27:00+08:00', 'trial'),
                  point('b', None, 'undated'), point('c', '2024-11-08T10:00:00Z', 'wait')]
        before = copy.deepcopy(points)
        result = derive_line(points)
        self.assertEqual(result['current_stance'], 'wait')
        self.assertEqual(result['stance_source_ids'], ['c'])
        self.assertEqual(result['time_span'], {'first': points[0]['source']['ts'], 'last': points[2]['source']['ts']})
        self.assertEqual(before, points)

    def test_missing_conflicting_or_rejected_latest_stance_never_falls_back(self):
        old = point('old', '2024-01-01', 'trial')
        for latest in (point('new', '2024-02-01'), point('new', '2024-02-01', 'wait', status='rejected'),
                       point('new', '2024-02-01', 'wait', suppressed_by='fiction-correction')):
            self.assertIsNone(derive_line([old, latest])['current_stance'])
        self.assertIsNone(derive_line([old, point('tie', '2024-01-01', 'wait')])['current_stance'])
        self.assertEqual(derive_line([old, point('tie', '2024-01-01', 'trial')])['current_stance'], 'trial')
        self.assertIsNone(derive_line([point('invalid', '2024-02-30', 'trial')])['time_span'])
        self.assertIsNone(derive_line([])['current_stance'])
        self.assertIsNone(derive_line([point('unknown')])['time_span'])

    def test_outcomes_and_shifts_count_points_without_new_inference(self):
        points = [point('a', outcomes=('confirmed', 'confirmed'), shift='reverse'),
                  point('b', outcomes=('refuted',), shift='same'),
                  point('c', outcomes=('confirmed', 'refuted'), shift='unclear'),
                  point('d', outcomes=('mixed',), shift='first'), point('e'),
                  point('f', outcomes=('confirmed',), shift='reverse', status='rejected')]
        derived = derive_line(points)
        self.assertEqual(derived['outcome_counts'], {'supported': 1, 'contradicted': 1, 'unknown': 4})
        self.assertEqual(derived['shift_count'], 1)
        home = derive_home([{'timeline': points}, {'timeline': points}], [])
        self.assertEqual(home['outcome_counts'], derived['outcome_counts'])
        self.assertEqual(home['point_count'], 6)
        self.assertEqual(home['shift_count'], 1)

    def test_safe_session_name_precedence_and_path_rejection(self):
        self.assertEqual(session_name('Fictional garden', {'title': 'Fallback'}), 'Fictional garden')
        self.assertEqual(session_name('', {'display_name': 'Fictional notes'}), 'Fictional notes')
        self.assertEqual(session_name(None, {'session_name': 'Fictional session'}), 'Fictional session')
        for value in ('C:/fictional/session.json', r'C:\fictional\notes', '/fictional/notes',
                      'file:///fictional', '../notes', 'notes.jsonl', 'folder/notes', 'C:notes', '~notes'):
            self.assertEqual(session_name(value, {'title': value, 'source_path': value}), '未命名会话')
        self.assertEqual(session_name(None, None), '未命名会话')

    def test_api_derives_after_visibility_and_corrections_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed(root)
            model = ReadModel(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            home = model.get('home', {})
            self.assertEqual(home['derived']['point_count'], 3)
            self.assertEqual(home['lines'][0]['derived']['shift_count'], 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            with contextlib.closing(sqlite3.connect(root / 'corpus.sqlite')) as db:
                db.execute('UPDATE documents SET channel=?,meta=?',
                           ('C:/fictional/session.json', json.dumps({'display_name': 'Fictional session'})))
                db.commit()
            evidence = model.get('evidence', {'kind': 'statements', 'id': 'fiction-s0'})
            self.assertEqual(evidence['derived']['session_display_name'], 'Fictional session')
            self.assertNotIn('C:/fictional', json.dumps(evidence))
            self.assertNotIn('"quote":', json.dumps(model.get('home', {})))

    def test_filtered_support_and_correction_precedence_reach_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed(root)
            graph = GraphStore(root)
            support = graph.get('statements', 'fiction-s1')
            support['sensitive'] = True
            graph.put('statements', support)
            # Add a latest proposition point whose status can be corrected.
            prop = graph.get('propositions', 'fiction-prop')
            prop['ts'] = '2025-04-01'
            graph.put('propositions', prop)
            line = graph.get('lines', 'fiction-line-1')
            line['timeline'].append({'statement_id':'fiction-prop', 'shift':'reverse', 'outcome':'unknown'})
            graph.put('lines', line)
            graph.close()
            journal = {'correction_id':'fiction-correction', 'prop_id':'fiction-prop',
                       'verdict':'wrong', 'note':'Fictional correction', 'observed_at':'2025-05-01'}
            (root / 'corrections.jsonl').write_text(json.dumps(journal)+'\n', encoding='utf-8')
            data = ReadModel(root).get('home', {})
            derived = data['lines'][0]['derived']
            self.assertEqual(derived['outcome_counts'], {'supported':0, 'contradicted':0, 'unknown':3})
            self.assertEqual(derived['shift_count'], 1)
            self.assertIsNone(derived['current_stance'])
            self.assertEqual(data['derived']['pending_count'], 0)
            self.assertEqual(data['derived']['confirmed_count'], 0)
            self.assertNotIn('fiction-s1', json.dumps(data))
            # Explicit visibility includes the stored support, but cannot undo correction.
            visible = ReadModel(root, sensitive=True).get('home', {})
            self.assertEqual(visible['derived']['outcome_counts']['supported'], 1)
            self.assertEqual(visible['derived']['pending_count'], 0)


class Round4DerivationTests(unittest.TestCase):
    def test_accuracy_threshold_and_stability_minimum(self):
        points = [point('a', outcomes=('confirmed',)), point('b', outcomes=('refuted',), shift='reverse')]
        self.assertIsNone(derive_line(points)['accuracy'])
        self.assertIsNone(derive_line(points)['stability'])
        self.assertEqual(derive_line(points)['accuracy_basis'], '已知 2 / 共 2')
        points.append(point('c', outcomes=('confirmed',)))
        result = derive_line(points)
        self.assertAlmostEqual(result['accuracy'], 2 / 3)
        self.assertEqual(result['stability'], 0.5)
        points.append(point('d', outcomes=('mixed',)))
        self.assertEqual(derive_line(points)['accuracy_basis'], '已知 3 / 共 4')
        self.assertEqual(derive_line([])['accuracy_basis'], '已知 0 / 共 0')
        self.assertEqual(derive_line([point(str(i)) for i in range(3)])['stability'], 1)
        points[1]['source']['status'] = 'rejected'
        self.assertEqual(derive_line(points)['reversal_count'], 0)
        self.assertIsNone(derive_line(points)['accuracy'])

    def test_pending_lexicographic_rank_unknowns_and_template(self):
        props = [dict(prop_id=i, text='虚构试种', status='proposed', confidence=c,
                      subject_node_ids=subjects, ts=ts)
                 for i, c, subjects, ts in [('a', .7, ['garden'], '2025-02-01'),
                                           ('b', .2, [], None),
                                           ('c', .2, ['garden'], '2025-01-01'),
                                           ('d', .2, ['garden'], '2025-03-01'),
                                           ('e', None, ['garden'], '2025-04-01')]]
        props.append(dict(props[0], prop_id='suppressed', suppressed_by='fiction'))
        before = copy.deepcopy(props)
        result = derive_pending([{'topic_node_id': 'garden', 'timeline': []}], props)
        self.assertEqual([p['prop_id'] for p in result], ['d', 'c', 'b', 'a', 'e'])
        self.assertEqual([p['priority'] for p in result], [1, 2, 3, 4, 5])
        self.assertEqual(result[0]['affected_line_count'], 1)
        self.assertIn('虚构试种', result[0]['question'])
        self.assertEqual(result[2]['recency_field'], None)
        self.assertEqual(props, before)
