"""Shell-free runner commands; concurrent processes, serialized queue operations."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from .queue import write_json

TEMPLATES = {
    "codex": ["codex", "exec", "-C", "{task_dir}", "-s", "workspace-write",
              "--skip-git-repo-check", "--ephemeral", "--output-schema",
              "{task_dir}/output.schema.json", "-o", "{task_dir}/output.json", "{prompt}"],
    "agy": ["agy", "-p", "{prompt}", "--output-format", "json", "--json-schema",
            "{task_dir}/output.schema.json", "--mode", "accept-edits", "--add-dir",
            "{task_dir}", "--print-timeout", "600s"],
    "grok": ["grok", "-p", "{prompt}", "--cwd", "{task_dir}", "--output-format",
             "json", "--json-schema", "{schema}", "--always-approve"],
}


def command(name, path, config):
    template = config.get("runners", {}).get(name, {}).get("cmd", TEMPLATES.get(name))
    if not isinstance(template, list) or not template or any(not isinstance(x, str) for x in template):
        raise ValueError("runner requires a nonempty cmd array")
    values = {"task_dir": str(path.resolve()), "python": sys.executable,
              "config_dir": config.get("config_dir", ""),
              "schema": (path / "output.schema.json").read_text(encoding="utf-8"),
              "prompt": "Read input.json and INSTRUCTIONS.md. Write output.json matching output.schema.json.\n"
                        + (path / "INSTRUCTIONS.md").read_text(encoding="utf-8")}
    # Replace only known placeholders, leaving literal JSON braces untouched.
    import re
    return [re.sub(r"\{(task_dir|python|config_dir|schema|prompt)\}",
                   lambda match: values[match[1]], item) for item in template]


def execute(argv, path, stdout_output, timeout):
    try:
        result = subprocess.run(argv, cwd=path, capture_output=True, timeout=timeout, check=False)
        if result.returncode:
            return [f"runner exited with code {result.returncode}"]
        if stdout_output:
            import json
            write_json(path / "output.json", json.loads(result.stdout))
        if not (path / "output.json").is_file():
            return ["runner did not produce output.json"]
        return []
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        # Never persist stdout/stderr or exception messages containing credentials.
        return ["runner failure: " + type(exc).__name__]


def run(queue, name, config, parallel=4, print_cmd=False, timeout=660):
    if parallel < 1 or timeout <= 0:
        raise ValueError("parallel and timeout must be positive")
    pending = [record for record in queue.list() if record["state"] == "pending"]
    if print_cmd:
        return [command(name, queue.locate(r["task_id"])[1], config) for r in pending]
    owner = "runner-" + uuid4().hex
    results = []
    # Claim at most parallel tasks at a time so leases cannot expire waiting
    # behind other jobs. Only this thread accesses SQLite or queue mutations.
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for offset in range(0, len(pending), parallel):
            jobs = {}
            for record in pending[offset:offset + parallel]:
                identifier = record["task_id"]
                command(name, queue.locate(identifier)[1], config)  # validate before claim
                queue.claim(identifier, owner, timeout + 60)
                path = queue.locate(identifier)[1]
                argv = command(name, path, config)
                jobs[pool.submit(execute, argv, path, name in ("agy", "grok"), timeout)] = (identifier, path)
            for future in as_completed(jobs):
                identifier, path = jobs[future]
                errors = future.result()
                if errors:
                    with queue.locked():
                        write_json(path / "errors.json", errors)
                        path.rename(queue.root / "rejected" / path.name)
                    results.append(dict(task_id=identifier, state="rejected", errors=errors))
                else:
                    results.append(queue.submit(identifier, path / "output.json", owner))
    return results
