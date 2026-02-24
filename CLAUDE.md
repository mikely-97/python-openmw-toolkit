# CLAUDE.md — OpenMW Addon Toolkit

## What is this?

- **`addon/`** — Python builder API for creating `.omwaddon` / `.omwgame` files
- **`tes3/`** — pure-stdlib binary parser/writer (zero deps) for TES3 format
- **`tools/`** — CLI: `omw-dump`, `omw-validate`, `omw-diff`

Run with `poetry run <cmd>` or activate `.venv/`.

## Reference docs

| Need to… | Read |
|----------|------|
| Understand TES3 binary format, all 42 record types, CELL/NPC flags | [docs/tes3-format.md](docs/tes3-format.md) |
| Use the Python builder or low-level reader/writer | [docs/builder-api.md](docs/builder-api.md) |
| Write Lua scripts, use world/inventory/spawn API | [docs/lua-api.md](docs/lua-api.md) |
| Write MWScript, configure openmw.cfg / settings.cfg | [docs/mwscript-cfg.md](docs/mwscript-cfg.md) |
| Diagnose a bug or avoid known pitfalls | [docs/gotchas.md](docs/gotchas.md) |

## Quickstart

```bash
poetry run omw-dump path/to/file.omwaddon --stats
poetry run omw-dump path/to/file.omwaddon --record NPC_
python hub_world/build.py          # build → hub_world.omwaddon
poetry run omw-validate hub_world/hub_world.omwaddon
poetry run omw-diff a.omwaddon b.omwaddon
# In-game console:
#   reloadlua   — hot-reload all .lua files without restarting
```

## Critical gotchas (always check before writing code)

- **`MODL`/`ITEX` paths omit `meshes/`/`icons/` prefix** — engine adds it. `"hub_world/foo.dae"` not `"meshes/hub_world/foo.dae"`.

- **Lua object properties are read-only** — `obj.position`, `.rotation`, `.scale` raise `"sol: cannot write to a readonly property"` from ALL script types. `world.setObjectEnabled` is a visual no-op on ACTI. Only reliable pattern: `obj:remove()` to hide; `world.createObject(id,1):teleport(cellName, pos)` to show.

- **`world.placeNewObject` is a no-op** in OpenMW 0.50. Use `world.createObject(recordId, 1):teleport(cellName, position)`.

- **`world.createObject(id, N>1)` triggers denomination lookup** — `createObject("Gold_001", 5)` looks for record `"gold_005"`. Always loop with `N=1`.

- **MWScript `SetAttribute`/`SetSkill` are invalid** — silently breaks the entire script. Use `ModAttribute`/`ModSkill`.

- **`EnableMenus` must compile cleanly** — a compile error breaks menus and spawn silently. Always test with a new game.

- **`onActivated` not `onActivate`** in LOCAL `engineHandlers` — wrong spelling is silently ignored.

See [docs/gotchas.md](docs/gotchas.md) for the full list including binary format hard errors and COLLADA issues.
