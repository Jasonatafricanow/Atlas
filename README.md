# ATLAS core

A **data-free** framework for turning a personal text corpus into browsable "lenses"
(judgment lines, timelines, correctable claim lists...). This repository contains
**no personal data and no default data paths**. Your corpus, private adapters,
private lenses and corrections live in a separate directory/repo you point to.

```
python -m atlas all --config examples/atlas.config.example.toml   # fictional demo
# open _demo_out/index.html
```

## Concepts
- **Document** (`atlas/schema.py`): the only data contract. `id, source, ts, text, author, channel, tags, meta`.
- **Adapter**: raw export -> Documents. Core ships only `jsonl_notes`. Chat-app exporters are private adapters.
- **Store**: `corpus.sqlite` inside `data_dir` (set via config or `ATLAS_DATA_DIR`).
- **Lens**: plugin `build(docs) -> JSON view`. All vocabularies/rules/prompts come from lens config files.
- **LLM**: `atlas.llm.Pipeline(provider, presend=[...])`; default `NullProvider` is offline.
  Redaction / sensitivity veto are optional `PreSend` hooks.
- **Frontend**: `web/index.html`, static, reads generated `data.js`. Holds no data.
- **Corrections**: `data_dir/corrections.jsonl` (`{"doc_id":..,"verdict":"wrong","note":..}`), shown on cards.

## Private setup (sketch)
```
my-atlas-private/            # private git repo, never public
  atlas.config.toml          # paths -> D:/atlas-data
  adapters/my_chat_export.py # class MyChatAdapter(atlas.adapters.Adapter)
  lenses/trade_ledger.py     # personal lenses
  lens_configs/*.json        # personal vocabularies
  run_daily.ps1              # python -m atlas all --config atlas.config.toml
```

## Leak safety
`git config core.hooksPath .githooks` enables `tools/leak_scan.py` before every commit.
Put private names in a denylist file outside the repo and set `ATLAS_LEAK_DENYLIST`.
