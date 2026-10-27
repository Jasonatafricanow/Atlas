"""Plugin loading: adapters and lenses are referenced as 'module:attr' or a
built-in short name. Private plugins are importable via [plugins].paths in config."""
import importlib, sys

BUILTIN_ADAPTERS = {"jsonl_notes": "atlas.adapters.jsonl_notes:JsonlNotesAdapter"}
BUILTIN_LENSES = {"timeline": "atlas.lenses.timeline:TimelineLens",
                  "judgment_lines": "atlas.lenses.judgment_lines:JudgmentLinesLens"}

def add_paths(paths):
    for p in paths or []:
        if p not in sys.path:
            sys.path.insert(0, p)

def load(ref, builtin):
    ref = builtin.get(ref, ref)
    mod, _, attr = ref.partition(":")
    return getattr(importlib.import_module(mod), attr)
