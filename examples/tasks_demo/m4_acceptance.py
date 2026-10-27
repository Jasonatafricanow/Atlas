"""M4 acceptance, isolated synthetic data and fake subprocesses only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    (ROOT / '_demo_out').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '_demo_out', prefix='m4-') as directory:
        base = Path(directory)
        env = dict(os.environ, ATLAS_DATA_DIR=str(base / 'data'), ATLAS_OUT_DIR=str(base / 'out'), ATLAS_LEAK_DENYLIST='')
        config = base / 'config.json'
        config.write_text(json.dumps({
            'sources': [{'adapter': 'jsonl_notes', 'options': {'path': str(ROOT / 'examples/synthetic_corpus/reading_notes.jsonl')}}],
            'runners': {'cmd': {'cmd': ['{python}', str(ROOT / 'examples/tasks_demo/fake_agent.py'), '--task-dir', '{task_dir}']}}
        }), encoding='utf-8')

        def cli(*args):
            argv = [sys.executable, '-m', 'atlas', *args, '--config', str(config)]
            result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
            print(' '.join(args))
            print(result.stdout)
            if result.returncode:
                raise AssertionError(result.stderr)
            return result.stdout

        cli('tasks', 'make', '--kind', 'extract_entities')
        for runner in ('codex', 'agy', 'grok'):
            commands = json.loads(cli('tasks', 'run', '--runner', runner, '--parallel', '4', '--print-cmd'))
            assert commands and commands[0][0] == runner
            argv = commands[0]
            if runner == 'codex':
                assert argv[1] == 'exec'
                assert all(flag in argv for flag in ('-C', '-s', '--skip-git-repo-check', '--ephemeral', '--output-schema', '-o'))
            else:
                assert argv[argv.index('--output-format') + 1] == 'json'
                if runner == 'agy':
                    assert argv[argv.index('--mode') + 1] == 'accept-edits'
                    assert argv[argv.index('--print-timeout') + 1] == '600s'
                    assert '--add-dir' in argv
                else:
                    assert json.loads(argv[argv.index('--json-schema') + 1])['type'] == 'object'
                    assert '--always-approve' in argv and '--cwd' in argv
        result = json.loads(cli('tasks', 'run', '--runner', 'cmd', '--parallel', '4'))
        assert result and all(r['state'] == 'accepted' for r in result)
        print('M4 CLI acceptance passed')

if __name__ == '__main__':
    main()
