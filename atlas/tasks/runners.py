"""Shell-free runner commands; concurrent processes, serialized queue operations."""
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from .queue import write_json

TEMPLATES = {
    "codex": ["codex", "exec", "-C", "{task_dir}", "-s", "workspace-write",
              "--skip-git-repo-check", "--ephemeral",
              "-o", "{task_dir}/last_message.txt", "-"],
    # No --output-schema: OpenAI strict structured output rejects optional keys
    # (e.g. relations[].supersedes). The agent writes output.json; ATLAS validates.
    "agy": ["agy", "-p", "{prompt_short}", "--output-format", "json", "--json-schema",
            "{task_dir}/output.schema.json", "--mode", "accept-edits", "--dangerously-skip-permissions", "--add-dir",
            "{task_dir}", "--print-timeout", "{timeout}s"],
    "grok": ["grok", "--prompt-file", "{prompt_file}", "--cwd", "{task_dir}", "--output-format",
             "json", "--json-schema", "{schema}", "--always-approve"],
}

# Templates whose full prompt is piped on stdin (avoids Windows argv limits and
# cmd.exe quoting of multi-line text when the program is a .cmd shim).
STDIN_PROMPT = {"codex"}
PROMPT_HEAD = ("Work only inside the current task directory. Read input.json and INSTRUCTIONS.md, "
               "then write output.json (UTF-8) matching output.schema.json. Prefer {doc_id, quote} "
               "evidence (exact excerpt, at most 60 characters). Do not compute hashes.\n")


def resolve_program(argv):
    """Resolve argv[0] via PATH/PATHEXT (finds npm .cmd shims) and wrap batch files."""
    program = argv[0]
    search = os.pathsep.join(_search_dirs())
    found = shutil.which(program, path=search)
    if not found and os.name == "nt":
        for suffix in (".cmd", ".exe", ".bat", ".ps1"):
            found = shutil.which(program + suffix, path=search)
            if found:
                break
    if not found:
        raise FileNotFoundError("runner program not found on PATH: " + os.path.basename(program))
    lower = found.lower()
    if lower.endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", found] + list(argv[1:])
    if lower.endswith(".ps1"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", found] + list(argv[1:])
    return [found] + list(argv[1:])


def _search_dirs():
    """PATH plus ATLAS_RUNNER_PATH and the default per-user install dirs of npm/agy/grok,
    which non-login shells on Windows often miss."""
    dirs = [d for d in os.environ.get("ATLAS_RUNNER_PATH", "").split(os.pathsep) if d]
    dirs += [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    home = os.path.expanduser("~")
    for base, sub in (("APPDATA", "npm"), ("LOCALAPPDATA", os.path.join("agy", "bin"))):
        if os.environ.get(base):
            dirs.append(os.path.join(os.environ[base], sub))
    dirs += [os.path.join(home, ".grok", "bin"), os.path.join(home, ".local", "bin")]
    return dirs


MODEL_FLAGS = {"codex": lambda m, e: (["-m", m] if m else []) + (["-c", f"model_reasoning_effort={e}"] if e else []),
               "agy": lambda m, e: (["--model", m] if m else []) + (["--effort", e] if e else []),
               "grok": lambda m, e: (["-m", m] if m else []) + (["--reasoning-effort", e] if e else [])}


def model_args(name, config, model=None, effort=None):
    """Explicit model/effort: CLI args override [runners.<name>] model/effort."""
    section = config.get("runners", {}).get(name, {})
    model, effort = model or section.get("model"), effort or section.get("effort")
    flags = MODEL_FLAGS.get(name)
    return flags(model, effort) if flags and (model or effort) else []


def command(name, path, config, timeout=600, model=None, effort=None):
    template = config.get("runners", {}).get(name, {}).get("cmd", TEMPLATES.get(name))
    if not isinstance(template, list) or not template or any(not isinstance(x, str) for x in template):
        raise ValueError("runner requires a nonempty cmd array")
    values = {"task_dir": str(path.resolve()), "python": sys.executable,
              "config_dir": config.get("config_dir", ""), "timeout": str(int(timeout)),
              "schema": (path / "output.schema.json").read_text(encoding="utf-8"),
              "prompt": prompt_text(path),
              "prompt_file": str((path / "PROMPT.md").resolve()),
              "prompt_short": "Read PROMPT.md in " + str(path.resolve()) + " and follow it exactly."}
    # Replace only known placeholders, leaving literal JSON braces untouched.
    import re
    argv = [re.sub(r"\{(task_dir|python|config_dir|schema|prompt_file|prompt_short|prompt|timeout)\}",
                   lambda match: values[match[1]], item) for item in template]
    extra = model_args(name, config, model, effort)
    if extra and argv and argv[-1] == "-":   # codex reads the prompt from stdin: keep "-" last
        return argv[:-1] + extra + ["-"]
    return argv + extra


def prompt_text(path):
    return PROMPT_HEAD + (path / "INSTRUCTIONS.md").read_text(encoding="utf-8")


def extract_json(text):
    """Parse agent stdout: raw JSON, a {result: ...} wrapper, or the last JSON object."""
    import json
    text = text.strip()
    try:
        value = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        try:
            value = json.loads(text[start:end + 1])
        except ValueError:
            # JSON followed by trailing prose or a second object: keep the first complete object.
            value = json.JSONDecoder().raw_decode(text[start:])[0]
    for key in ("structured_output", "structuredOutput", "result", "output", "response", "text"):
        if isinstance(value, dict) and key in value and not {"entities", "operations", "decisions"} & set(value):
            inner = value[key]
            if isinstance(inner, str):
                try:
                    return extract_json(inner)
                except ValueError:
                    continue
            if isinstance(inner, dict):
                return inner
    return value


def _looks_mojibake(text):
    import re
    return "\ufffd" in text or re.search(r"\?{4,}", text) is not None


def execute(argv, path, stdout_output, timeout, stdin_text=None):
    try:
        (path / "PROMPT.md").write_text(prompt_text(path), encoding="utf-8")
        argv = resolve_program(argv)
        result = subprocess.run(argv, cwd=path, capture_output=True, timeout=timeout, check=False,
                                input=stdin_text.encode("utf-8") if stdin_text is not None else None,
                                stdin=None if stdin_text is not None else subprocess.DEVNULL)
        from .guard import redact
        # Diagnostics stay in the private task dir, credential-redacted, tail only.
        (path / "runner.log").write_text(redact(result.stderr.decode("utf-8", "replace")[-4000:]), encoding="utf-8")
        if result.returncode:
            return [f"runner exited with code {result.returncode}"]
        if stdout_output:
            import json
            write_json(path / "output.json", extract_json(result.stdout.decode("utf-8", "replace")))
        last = path / "last_message.txt"
        if not (path / "output.json").is_file() and last.is_file():
            try:
                write_json(path / "output.json", extract_json(last.read_text(encoding="utf-8")))
            except ValueError:
                pass
        if not (path / "output.json").is_file():
            return ["runner did not produce output.json"]
        if _looks_mojibake((path / "output.json").read_text(encoding="utf-8", errors="replace")):
            return ["output.json looks encoding-corrupted (runs of '?' or U+FFFD); rerun the task"]
        return []
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        # Never persist stdout/stderr or exception messages containing credentials.
        return ["runner failure: " + type(exc).__name__]


def _uses_stdin(name, config):
    override = config.get("runners", {}).get(name, {}).get("stdin")
    return bool(override) if override is not None else name in STDIN_PROMPT


def run(queue, name, config, parallel=4, print_cmd=False, timeout=660, model=None, effort=None):
    if parallel < 1 or timeout <= 0:
        raise ValueError("parallel and timeout must be positive")
    pending = [record for record in queue.list() if record["state"] == "pending"]
    if print_cmd:
        return [command(name, queue.locate(r["task_id"])[1], config, timeout, model, effort) for r in pending]
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
                argv = command(name, path, config, max(1, timeout - 30), model, effort)
                stdin_text = prompt_text(path) if _uses_stdin(name, config) else None
                jobs[pool.submit(execute, argv, path, name in ("agy", "grok"), timeout, stdin_text)] = (identifier, path)
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
