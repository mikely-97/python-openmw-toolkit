# Gotchas — Confirmed Issues (OpenMW 0.50)

## General / Binary Format

- **IDs are case-insensitive** in the engine. Always use lowercase in new content.
- **Strings are null-terminated** (`\x00`). The reader strips them; the writer adds them automatically.
- **Interior CELLs** use `NAME` as their identifier. Exterior cells use `(grid_x, grid_y)` from `CELL/DATA`. Interior flag (0x01) must be set.
- **NPC_ autocalc**: when the `0x0008` flag is set, the engine ignores explicit stats in `NPDT`. Use the 12-byte short form of `NPDT`.
- **MAST/DATA pairs**: the file size in `DATA` is checked by some tools but OpenMW only warns on mismatch. Pass 0 if unknown.
- **DIAL/INFO ordering**: `INFO` records form a linked list via `PNAM`/`NNAM`. They must appear in the file after their parent `DIAL`. Order matters.
- **`MODL` / `ITEX` paths** omit the leading `meshes/` or `icons/` prefix — the engine adds it. Storing the full path causes a double-prefix: `Failed to load 'meshes/meshes/x/myobj.nif'`.
- **`CELL/AMBI` color bytes** must be packed as `[R, G, B, A]` (R at lowest address). `struct.pack("<I", 0x888888FF)` puts A=0xFF at byte 0 → OpenMW reads it as solid red. Correct: `struct.pack("<BBBB", r, g, b, a)` where input is 0xRRGGBBAA.
  Also: fog_density must be `struct.pack("<f", density)` (float32), not an integer.
- **Dialogue text strings must be latin-1 encodable**. Em dashes (`—`), curly quotes etc. raise `UnicodeEncodeError` at build time. Use ` - ` instead of ` — `, `"` instead of `"`.

## Binary Format Hard Errors (crash at load)

- **`CELL/DATA` must be exactly 12 bytes** — `struct.pack("<Iii", flags, grid_x, grid_y)`. Writing 16 bytes (`<IIii`) causes: `ESM Error: record size mismatch, requested 12, got 16`.
  Also: `CELL/DATA` tag is overloaded — 12 bytes = cell header, 24 bytes = object position (`<ffffff` x,y,z,rx,ry,rz).

- **`CONT/FLAG` bit 3 (0x08) must always be set** — even for plain containers. Builder defaults to `0x08`. Omitting causes: `ESM Error: Flag 8 not set`.

- **`MISC/MCDT` must be exactly 12 bytes** — `struct.pack("<fII", weight, value, flags)`. Using 10 bytes (`<fIH`) causes a size mismatch crash.

- **`NPC_/NPDT` autocalc form must be exactly 12 bytes** — `struct.pack("<HBBBxxxI", level, disposition, reputation, rank, gold)`: level(H=2) + disposition(B=1) + reputation(B=1) + rank(B=1) + 3 padding + gold(I=4) = 12.

- **`NPC_/AIDT` must be exactly 12 bytes** — `struct.pack("<BBBBBBBBI", hello, fight, flee, alarm, u1, u2, u3, u4, services)`: 4×B + 4×padding + services(I=4) = 12. Using `<BBBBI` (8 bytes) crashes.

- **`LIGH/LHDT` must be exactly 24 bytes** — `struct.pack("<fIiiBBBBI", weight, value, duration, radius, r, g, b, pad, flags)` = 24 bytes. Using 20 bytes (omitting flags from `I` to `B`) crashes.

- **`SCPT` subrecord layout**:
  - `SCHD` must be **52 bytes**: `struct.pack("<32sIIIII", name, num_shorts, num_longs, num_floats, script_data_size, local_var_size)`. Missing `local_var_size` (48 bytes) crashes.
  - `SCDT` (compiled bytecode) must be present, even if empty (`b""`). Omitting it crashes.
  - `SCTX` (source text) must be raw bytes **without** a null terminator.

- **`INFO/DATA` must be exactly 12 bytes** — `struct.pack("<iibbbb", type, disposition, npc_rank, gender, pc_rank, 0)`. Using `<BBBI` (7 bytes) crashes. Use -1 for npc_rank/gender/pc_rank to mean "any".

## Lua Runtime Issues (OpenMW 0.50)

- **`onActivated` not `onActivate`** in LOCAL `engineHandlers`. Wrong spelling silently does nothing.

- **Object properties are read-only from ALL Lua script types** — `obj.position`, `.rotation`, `.scale` all raise `"sol: cannot write to a readonly property"` in both GLOBAL and LOCAL scripts. `world.setObjectEnabled(obj)` exists but **has no visual effect on ACTI objects** (silent no-op).
  **Only reliable hide/show pattern:** `obj:remove()` to hide; `world.createObject(id, 1):teleport(cellName, pos)` to show.

- **`world.placeNewObject` is a no-op in OpenMW 0.50**. Runs without error, no visible result. Use `world.createObject(recordId, 1):teleport(cellName, position)` instead. `teleport` on a disabled (newly created) object places and enables it atomically. Cell name can be a plain string.

- **`world.createObject(id, N)` with N > 1 triggers gold denomination lookup** — `createObject("Gold_001", 5)` makes the engine search for record "gold_005". Affects any ID ending in `_00N`. Always loop with N=1:
  ```lua
  for i = 1, amount do world.createObject(id, 1):moveInto(inv) end
  ```

- **`types.Actor.inventory(actor):add(id, count)` does not exist in OpenMW 0.50**. Inventory only exposes `countOf`, `find`, `findAll`, `getAll`, `isResolved`, `resolve`. Correct pattern (GLOBAL only):
  ```lua
  world.createObject(id, 1):moveInto(types.Actor.inventory(actor))  -- give
  types.Actor.inventory(actor):find(id):remove(count)               -- take
  ```

- **`core.getGameTimeInSeconds()` does not exist in OpenMW 0.50 Flatpak**. Wrap in `pcall` with fallback: `realTimeAccum * 30`.

- **`openmw.async:newTimerInRealSeconds` is not available in GLOBAL scripts in OpenMW 0.50**. Use an `onUpdate` handler with accumulated dt instead.

- **Hot-reload Lua**: type `reloadlua` in the OpenMW in-game console. Only works for loose `.lua` files. Requires a fresh game or save reload for `.omwaddon` changes.

## MWScript Issues

- **`SetAttribute` and `SetSkill` are not valid MWScript commands**. If used, OpenMW fails to compile the entire script silently — no error shown in-game, all functionality in that script breaks. The correct commands are `ModAttribute` and `ModSkill` (they add to the current base value).

- **`EnableMenus` must compile cleanly**. If our override has a compile error, OpenMW skips it entirely and falls back to the template's version — or breaks menus. The player spawns at the wrong location with no diagnostic. Always test with a new game after any EnableMenus change.

- **Player spawn is controlled by the `EnableMenus` MWScript** (not `sStartCell` GMST alone). Override it to redirect spawn:
  ```
  Begin EnableMenus
  EnableMagicMenu
  EnableInventoryMenu
  EnableMapMenu
  EnableStatsMenu
  EnableRest
  set CharGenState to -1
  Player->PositionCell 0, -300, 0, 0, "YourCellName"
  stopscript EnableMenus
  End EnableMenus
  ```

## COLLADA Mesh Issues

- **Materials must use `<blinn>`** (not `<lambert>`). OpenMW requires `<blinn>` with `<emission>`, `<ambient>`, `<diffuse>`, `<specular>`, `<shininess>`. Using `<lambert>` gives solid red fallback.

- **`<bind_vertex_input>` must use `semantic=`, not `symbol=`**. Using `symbol` crashes OpenMW with SIGSEGV (signal 11, address nil). Correct:
  ```xml
  <instance_material symbol="floor" target="#Mat_floor">
    <bind_vertex_input semantic="CHANNEL1" input_semantic="TEXCOORD" input_set="0"/>
  </instance_material>
  ```

- **`<init_from>` paths are absolute VFS paths**, not relative to the DAE. A DAE at `meshes/hub_world/foo.dae` with `<init_from>textures/hw_white.dds</init_from>` looks up from the VFS root.

- **Rotating a STAT via `rot_z` does not rotate its UV mapping**. Generate separate pre-oriented meshes (e.g. `wall_hub.dae` for N/S, `wall_hub_ew.dae` for E/W) and place with no rotation.

- **NPC meshes must use the skeleton from `basicplayer.dae`**. A custom DAE with no skeleton bindings collapses all geometry to the origin (unclickable blob). Pattern: STAT for visual + NPC with `mesh="basicplayer.dae"` placed in front.

- **Use the Flatpak OpenMW**, not the system package. System package ships an `osgdb_dae.so` incompatible with OpenMW 0.50's VFS — every `.dae` fails.

## Lua UI Limitations

- **`ui.TYPE.Window` chrome does not render reliably** — frame, title bar, and close button may be invisible. Content (Text/Flex children) renders as a floating overlay with no background or border.

- **Mouse events do not fire during gameplay** — `events = { mouseClick = ... }` on `ui.TYPE.Widget` requires the cursor to be visible. In normal gameplay the cursor is captured by the camera. Reliable pattern: **keyboard-driven menus** using `onKeyPress` in the PLAYER `engineHandlers`. Use digit keys 1-N to select, Escape/0 to close.

- **`ui.TYPE.Window` is not the MyGUI barter/dialog window** — barter, dialogue, inventory etc. are native engine windows, not replicable from Lua. `ui.TYPE.Window` is a Lua overlay widget only.

## Known Non-Fatal Example Suite Warnings

Pre-existing, don't try to fix:

| Warning | Source | Reason |
|---------|--------|--------|
| `Can't find texture: textures/menu_small_energy_bar_*.dds` | engine UI | Example suite never ships HUD textures |
| `nif load failed: meshes/ashcloud.nif` (and blightcloud, snow, blizzard) | weather | No weather meshes in template |
| `Can't find texture: textures/hu_male.dds` | `BasicPlayer.dae` | Referenced but not committed |
| `Cell reference 'raceryo' not found` | `the_hub.omwaddon` | Pre-existing removed/renamed object |
| `LandRacer: bind_material not found for geometry CHANNEL1` | `landracer.omwaddon` | DAE binding issue in upstream asset |
| `LandRacer: no bone … in skeleton` | `landracer.omwaddon` | Bone name mismatch in upstream asset |
