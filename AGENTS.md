# Agent instructions

Read docs/CODEX_BRIEF.md completely before work. Implement only the milestone
explicitly requested. M1-M5 are implemented; M6 is optional and not authorized
by an M5 task.

- Use `C:\Python314\python.exe`; standard library only, with optional jsonschema.
- Use only fictional examples. Never read real user data, chat exports, old
  ATLAS directories, or a real ATLAS_DATA_DIR. Demo output belongs in `_demo_out/`
  or a disposable temporary directory. Explicitly set demo environment paths.
- Never commit personal content, credentials, runtime databases or task workspaces.
- Do not call paid APIs. Runner tests use the local fake agent only.
- Do not weaken tools/leak_scan.py or .githooks. Never bypass pre-commit.
- Do not git push. Finish an authorized milestone with acceptance checks and one
  local commit as requested by the user.
- Preserve evidence pointers and correction precedence; do not invent source
  facts, timestamps, stance changes or graph records for an empty graph.

Task contracts, offline demo commands, and correction export are documented in
[docs/AGENT_TASKS.md](docs/AGENT_TASKS.md).
