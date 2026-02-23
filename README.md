# OpenMW Addon Toolkit

A Python toolkit for authoring `.omwgame` / `.omwaddon` files (TES3 binary format) for OpenMW.

## Quickstart

```bash
poetry install
poetry run omw-dump path/to/file.omwaddon
poetry run omw-dump path/to/file.omwaddon --record NPC_ --json
```

See [CLAUDE.md](CLAUDE.md) for the full LLM-oriented reference.
