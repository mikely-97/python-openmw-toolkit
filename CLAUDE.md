# CLAUDE.md — OpenMW Addon Toolkit: LLM Reference

This is the primary context document for working in this repository.
Read it in full before writing any code.

---

## 1. What Is This Repo?

A self-contained Python toolkit for creating and modifying OpenMW addon files
(`.omwaddon` / `.omwgame`) from Python code. It has two layers:

- **`tes3/`** — pure-stdlib binary parser/writer (zero deps).
  Use this for reading existing files, round-tripping, or when you need raw
  record access.
- **`addon/`** — high-level builder API. Use this for creating new content.
- **`tools/`** — CLI scripts: `omw-dump`, `omw-validate`, `omw-diff`.

Run with `poetry run <command>` or activate the venv at `.venv/`.

---

## 2. Quickstart Workflow

```bash
# 1. Inspect an existing file
poetry run omw-dump path/to/file.omwaddon --stats
poetry run omw-dump path/to/file.omwaddon --record NPC_
poetry run omw-dump path/to/file.omwaddon --json > dump.json

# 2. Write an addon using the builder API
python my_addon.py   # produces my_addon.omwaddon

# 3. Validate
poetry run omw-validate my_addon.omwaddon

# 4. Compare two versions
poetry run omw-diff original.omwaddon modified.omwaddon

# 5. Drop into openmw.cfg
#   data="path/to/addon/folder"
#   content=my_addon.omwaddon
```

---

## 3. TES3 Binary Format Cheat Sheet

`.omwgame` / `.omwaddon` are the **TES3 binary format** (same as Morrowind
`.esm` / `.esp`). All integers are **little-endian**.

### Record header — 16 bytes

| Offset | Size | Field  | Description                          |
|--------|------|--------|--------------------------------------|
| 0      | 4    | tag    | ASCII, e.g. `TES3`, `NPC_`, `CELL`  |
| 4      | 4    | size   | uint32 — byte count of payload only  |
| 8      | 4    | hdr1   | uint32 — flags (usually 0)           |
| 12     | 4    | flags  | uint32 — 0x400=Persistent, 0x2000=Blocked |

### Subrecord header — 8 bytes

| Offset | Size | Field | Description                         |
|--------|------|-------|-------------------------------------|
| 0      | 4    | tag   | ASCII, e.g. `NAME`, `DATA`, `FNAM`  |
| 4      | 4    | size  | uint32 — byte count of data         |

### TES3 header record

Always the first record. Contains:
- `HEDR` (300 bytes): `float version` (1.3), `uint file_type` (0=esp/omwaddon,
  1=esm/omwgame, 32=save), `char[32] company`, `char[256] description`,
  `uint num_records`.
- Zero or more `MAST`/`DATA` pairs: master filename + uint64 file size.

### String encoding

Most strings are **null-terminated**, encoding **latin-1** (ISO-8859-1).
Fixed-width fields (HEDR company/description) are null-padded to their width.
IDs are **case-insensitive** in the engine — use lowercase consistently.

---

## 4. Record Type Reference

All 42 TES3 record types. Tags marked `*` have full schema coverage in
`tes3/schema.py`; others store unknown subrecords as raw bytes (transparent
round-trip).

| Tag    | Represents           | Key subrecords                                    |
|--------|----------------------|---------------------------------------------------|
| `TES3` | File header          | HEDR, MAST/DATA pairs                             |
| `GMST` | Game setting         | NAME (id), STRV/INTV/FLTV (value)                 |
| `GLOB` | Global variable      | NAME, FNAM (type char), FLTV (value)              |
| `CLAS` | Character class      | NAME, FNAM, CLDT (struct), DESC                   |
| `FACT` | Faction              | NAME, FNAM, FADT (struct), ANAM (ranks)           |
| `RACE` | Race                 | NAME, FNAM, RADT (struct), DESC                   |
| `SOUN` | Sound                | NAME, FNAM (wav path), DATA (vol/range)            |
| `SKIL` | Skill                | INDX, SKDT, DESC                                  |
| `MGEF` | Magic effect         | INDX, MEDT, ITEX, PTEX, sounds, CVFXs             |
| `SCPT` | MWScript             | SCHD, SCVR, SCDT (bytecode), SCTX (source)        |
| `REGN` | Region               | NAME, FNAM, WEAT, BNAM, CNAM, SNAM                |
| `BSGN` | Birthsign            | NAME, FNAM, TNAM, DESC, NPCS                      |
| `LTEX` | Land texture         | NAME, INTV (index), DATA (tex path)               |
| `STAT` | Static object        | NAME, MODL (mesh path)                            |
| `DOOR` | Door                 | NAME, MODL, FNAM, SCRI, SNAM, ANAM                |
| `MISC` | Misc. item           | NAME, MODL, FNAM, MCDT, SCRI, ITEX                |
| `WEAP` | Weapon               | NAME, MODL, FNAM, WPDT, ITEX, ENAM, SCRI          |
| `CONT` | Container            | NAME, MODL, FNAM, CNDT, FLAG, SCRI, NPCO×         |
| `SPEL` | Spell                | NAME, FNAM, SPDT, ENAM×                           |
| `CREA` | Creature             | NAME, MODL, FNAM, SCRI, NPDT, AIDT, NPCO×        |
| `BODY` | Body part            | NAME, MODL, FNAM, BYDT                            |
| `LIGH` | Light                | NAME, MODL, FNAM, LHDT, ITEX, SCRI, SNAM          |
| `ENCH` | Enchantment          | NAME, ENDT, ENAM×                                 |
| `NPC_` | NPC                  | NAME, FNAM, RNAM, CNAM, ANAM, BNAM, KNAM, NPDT, FLAG, AIDT, NPCO×, NPCS× |
| `ARMO` | Armour               | NAME, MODL, FNAM, AODT, ITEX, INDX/BNAM/CNAM×    |
| `CLOT` | Clothing             | NAME, MODL, FNAM, CTDT, ITEX, INDX/BNAM/CNAM×    |
| `REPA` | Repair tool          | NAME, MODL, FNAM, RIDT, ITEX, SCRI                |
| `ACTI` | Activator            | NAME, MODL, FNAM, SCRI                            |
| `APPA` | Apparatus            | NAME, MODL, FNAM, AADT, ITEX, SCRI                |
| `LOCK` | Lockpick             | NAME, MODL, FNAM, LKDT, ITEX, SCRI                |
| `PROB` | Probe                | NAME, MODL, FNAM, PBDT, ITEX, SCRI                |
| `INGR` | Ingredient           | NAME, MODL, FNAM, IRDT, ITEX, SCRI                |
| `BOOK` | Book / scroll        | NAME, MODL, FNAM, BKDT, SCRI, ITEX, ENAM, TEXT    |
| `ALCH` | Potion               | NAME, MODL, FNAM, ALDT, SCRI, ITEX, ENAM×         |
| `LEVI` | Levelled item list   | NAME, DATA, NNAM, INDX, INAM×/INTV× pairs         |
| `LEVC` | Levelled creature    | NAME, DATA, NNAM, INDX, CNAM×/INTV× pairs         |
| `CELL` | Cell (int/ext)       | NAME, DATA, AMBI, WHGT, RGNN; then FRMR/NAME/DATA× |
| `LAND` | Landscape            | INTV (grid), DATA, VNML, VHGT, VCLR, VTEX         |
| `PGRD` | Pathgrid             | DATA, NAME, PGRP, PGRC                            |
| `SNDG` | Sound generator      | NAME, DATA, SNAM, CNAM                            |
| `DIAL` | Dialogue topic       | NAME, DATA (type)                                 |
| `INFO` | Dialogue response    | INAM, PNAM, NNAM, DATA, speaker filters, NAME (text), BNAM (script) |

### CELL flags (DATA subrecord, uint32)

| Bit  | Hex    | Meaning                        |
|------|--------|--------------------------------|
| 0    | 0x0001 | Interior cell                  |
| 1    | 0x0002 | Has water                      |
| 2    | 0x0004 | Illegal to sleep               |
| 7    | 0x0080 | Behave like exterior           |

### NPC_ flags (FLAG subrecord, uint32)

| Bit  | Hex    | Meaning             |
|------|--------|---------------------|
| 0    | 0x0001 | Female              |
| 1    | 0x0002 | Essential           |
| 2    | 0x0004 | Respawn             |
| 3    | 0x0008 | Autocalc stats      |
| 10   | 0x0400 | Skeleton blood      |
| 11   | 0x0800 | Metal blood         |

### NPC_ NPDT — two layouts

- **Autocalc (12 bytes):** `H level`, `B disposition`, `B faction_rank`,
  `6B unknown`, `I gold`
- **Full (52 bytes):** level, all 8 attributes, 27 skill values, reputation,
  health, max_magicka, fatigue, disposition, faction_id, rank, unknown, gold

Use autocalc for NPCs where you don't care about exact stats.

---

## 5. Builder API — `addon/builder.py`

```python
from addon import AddonBuilder

addon = AddonBuilder(
    description="My addon",
    company="My Studio",
    masters=["template.omwgame"],   # or list of (name, size) tuples
    file_type=0,                    # 0=addon, 1=master
)

# Global variable
addon.add_global("MyMod_Version", type="short", value=1)
# type: 'short'|'long'|'float'  (or 's'|'l'|'f')

# NPC
addon.add_npc(
    id="mymod_merchant_01",
    name="Bob the Merchant",
    race="Breton",
    npc_class="Merchant",
    faction="",
    disposition=60,
    level=5,
    gold=500,
    flags=["autocalc"],
    services=0x0004,        # barter
    inventory=[("iron longsword", 1), ("bread", 5)],
    spells=["almsivi intervention"],
    mesh="",                # leave blank to use race default
)

# Static object (mesh reference only — actual .nif lives in VFS)
addon.add_static("mymod_pillar_01", mesh="meshes/x/mymod_pillar.nif")

# Light
addon.add_light(
    id="mymod_candle_01",
    radius=100,
    color=(255, 200, 120),
    flags=["dynamic", "fire", "can_carry"],
    duration=3600,
)

# Container
addon.add_container(
    id="mymod_chest_01",
    name="Old Chest",
    capacity=200.0,
    inventory=[("Gold_001", 50)],
)

# Misc item
addon.add_misc_item(
    id="mymod_key_01",
    name="Rusty Key",
    weight=0.1,
    value=5,
)

# Book
addon.add_book(
    id="mymod_tome_01",
    name="Tome of Secrets",
    text="<DIV ALIGN=CENTER>The secrets are...</DIV>",
    weight=2.0,
    value=100,
)

# Spell (spell_type: 0=spell, 1=ability, 2=blight, 3=disease, 4=curse, 5=power)
addon.add_spell(
    id="mymod_fire_bolt",
    name="Fire Bolt",
    spell_type=0,
    cost=10,
    effects=[{
        "effect_id": 14,       # Fireball = 14
        "range": 0,            # 0=self, 1=touch, 2=target
        "area": 0,
        "duration": 1,
        "magnitude_min": 10,
        "magnitude_max": 20,
    }],
)

# MWScript (OpenMW compiles SCTX on load)
addon.add_script(
    id="mymod_my_script",
    source="Begin mymod_my_script\n; ...\nEnd",
    num_shorts=1,
    variables=["myvar"],
)

# Game setting override
addon.add_game_setting("fJumpHeightMin", 50.0)
addon.add_game_setting("iNumberCreaturesAttackMe", 3)
addon.add_game_setting("sLevelUpMsg", "You levelled up!")

# Levelled list
addon.add_levelled_list(
    id="mymod_random_loot",
    items=[("iron dagger", 1), ("gold_005", 1)],
    chance_none=10,
    flags=0x01,     # 0x01=calc from all levels ≤ PC, 0x02=calc for each item
)

# Dialogue
addon.add_dialogue_topic(
    name="the meaning of life",
    topic_type=0,   # 0=topic, 1=voice, 2=greeting, 3=persuasion, 4=journal
    responses=[{
        "id": "mymod_info_0001",
        "prev_id": "",
        "next_id": "",
        "text": "Forty-two.",
        "speaker_id": "mymod_merchant_01",
    }],
)

# Interior cell
cell = addon.add_interior_cell(
    "My Shop",
    flags=["illegal_to_sleep"],
    ambient=0x404040FF,     # RGBA as uint32
    fog_color=0x000000FF,
    fog_density=0.5,
    water_height=0.0,
)
cell.place_npc("mymod_merchant_01", x=0, y=128, z=0, rotation=0)
cell.place_static("mymod_pillar_01", x=300, y=0, z=0)
cell.place_container("mymod_chest_01", x=200, y=0, z=0)
cell.place_light("mymod_candle_01", x=0, y=0, z=180)
cell.place_door(
    "mymod_door_01",
    x=0, y=-300, z=0,
    destination_cell="The Hub",
    destination_pos=(0, 0, 0),
)
cell.place_item("mymod_key_01", x=100, y=50, z=0)

# Exterior cell
ext_cell = addon.add_exterior_cell(grid_x=5, grid_y=3, region="Grazelands")

# Append a hand-crafted record dict (escape hatch)
addon.append_raw_record({
    "tag": "GMST",
    "flags": 0,
    "hdr1": 0,
    "subrecords": [
        {"tag": "NAME", "raw": b"sLevelUpMsg\x00"},
        {"tag": "STRV", "raw": b"Level up!\x00"},
    ],
})

# Save
addon.save("mymod.omwaddon")

# Or get bytes
data: bytes = addon.to_bytes()
```

---

## 6. Low-Level API — `tes3/reader.py` and `tes3/writer.py`

```python
from tes3.reader import read_file, read_bytes
from tes3.writer import write_file, write_bytes

# Parse
records = read_file("file.omwaddon")

# Record dict structure
# {
#     "tag": "NPC_",
#     "flags": 0,
#     "hdr1": 0,
#     "subrecords": [
#         {"tag": "NAME", "raw": b"ra'virr\x00", "parsed": "ra'virr"},
#         {"tag": "FLAG", "raw": b"\x00\x00\x00\x00", "parsed": {"flags": 0}},
#         {"tag": "NPDT", "raw": b"...52 bytes..."},  # no "parsed" = raw-only
#     ]
# }

# Modify and re-serialize
for rec in records:
    if rec["tag"] == "GLOB":
        for sr in rec["subrecords"]:
            if sr["tag"] == "FLTV":
                import struct
                sr["raw"] = struct.pack("<f", 99.0)

write_file(records, "modified.omwaddon")

# Round-trip is bit-identical (the writer always uses "raw" bytes)
```

---

## 7. MWScript Reference

MWScript is the classic Morrowind scripting language. Scripts are stored in
`SCPT` records with source in `SCTX` and (optionally) compiled bytecode in
`SCDT`. OpenMW can compile source-only scripts on load.

```
Begin script_id

short local_var
float local_float

if ( GetItemCount "item_id" > 0 )
    MessageBox "You have the item!"
    set local_var to 1
endif

; Attach to NPC/CONT/DOOR via SCRI subrecord on those records
; Global scripts: listed in SCPT, auto-run via StartScripts mechanism

End
```

Common functions: `MessageBox`, `GetItemCount`, `AddItem`, `RemoveItem`,
`GetCurrentAIPackage`, `AITravel`, `AIFollow`, `AIWander`, `StartScript`,
`StopScript`, `SetGlobal`, `GetGlobal`, `MenuMode`, `OnActivate`,
`PCGetRace`, `PCGetClass`, `PCGetFaction`.

---

## 8. Lua Scripting Reference

Lua scripts are **not stored in the addon binary**. They are loose `.lua`
files registered by a `.omwscripts` manifest file.

### Script types

| Type   | Flag        | Always active? | API access               |
|--------|-------------|---------------|--------------------------|
| GLOBAL | `GLOBAL`    | Yes           | openmw.world (read-write)|
| MENU   | `MENU`      | Yes (pre-game)| openmw.ui, openmw.input  |
| PLAYER | `PLAYER`    | On player     | openmw.ui, openmw.nearby |
| LOCAL  | `NPC` etc.  | When loaded   | openmw.nearby (read-only)|
| CUSTOM | `CUSTOM`    | When attached | openmw.nearby (read-only)|

### .omwscripts format

```
# Comment
GLOBAL: scripts/mymod/global.lua
PLAYER: scripts/mymod/player.lua
NPC, CREATURE: scripts/mymod/actor_ai.lua
CUSTOM: scripts/mymod/attachable.lua
```

Register in `openmw.cfg` as: `content=mymod.omwscripts`

### Script template

```lua
local core = require('openmw.core')
local self = require('openmw.self')   -- LOCAL/PLAYER only

local function onInit(data)   end  -- first time only
local function onSave()       return {} end
local function onLoad(data)   end
local function onUpdate(dt)   end  -- every frame
local function onActivate(object, actor) end

return {
    engineHandlers = {
        onInit = onInit,
        onSave = onSave,
        onLoad = onLoad,
        onUpdate = onUpdate,
        onActivate = onActivate,
    }
}
```

### Key API packages

- `openmw.core` — all types: time, types, sendGlobalEvent, getGameTime
- `openmw.world` — GLOBAL: spawn, remove, teleport, get/setObjectActive
- `openmw.nearby` — LOCAL/PLAYER: objects in loaded range
- `openmw.self` — LOCAL/PLAYER: the object this script runs on
- `openmw.ui` — PLAYER/MENU: widgets, text, HUD
- `openmw.camera` — PLAYER: camera control
- `openmw.input` — PLAYER/MENU: keyboard/mouse
- `openmw.storage` — all: persist tables across sessions
- `openmw.types` — all: Actor, NPC, Weapon, … type-specific methods
- `openmw.util` — all: math, vectors, transforms
- `openmw.async` — all: timers, coroutines
- `openmw.vfs` — all: read VFS data files
- `openmw.ambient` — PLAYER: ambient sound
- `openmw.animation` — LOCAL/PLAYER: animation playback

---

## 9. openmw.cfg Load Order

```ini
data="path/to/game_template"
data="path/to/my_addon_folder"

content=template.omwgame        # base game (must come first)
content=my_addon.omwaddon       # your addon
content=my_addon.omwscripts     # your Lua scripts (separate line)
```

- `data=` paths form the VFS; assets (meshes, textures) are looked up here.
- `content=` entries load in order; later files override earlier ones.
- `.omwscripts` must be a separate `content=` entry from `.omwaddon`.

### Which OpenMW installation to use

**Use the Flatpak release** (`org.openmw.OpenMW`), not the system package.

The system `openmw` package on Void Linux (and likely other distros) ships an
`osgPlugins-3.6.5/osgdb_dae.so` that is incompatible with how OpenMW 0.50
reads COLLADA files through its VFS — every `.dae` file fails with
`Extra content at the end of the document` / `Load failed in COLLADA DOM`.
The Flatpak bundles its own matching osg+collada-dom and works correctly.

Run via:
```bash
flatpak run --command=openmw org.openmw.OpenMW [args...]
```

Flatpak config lives at `~/.var/app/org.openmw.OpenMW/config/openmw/`.

### Full example-suite setup (flatpak `openmw.cfg`)

`~/.var/app/org.openmw.OpenMW/config/openmw/openmw.cfg`:

```ini
encoding=win1252

data="/path/to/example-suite/game_template/data"
data="/path/to/example-suite/the_hub/data"
data="/path/to/example-suite/example_animated_creature/data"
data="/path/to/example-suite"           # for addons at the suite root

content=template.omwgame
content=the_hub.omwaddon
content=landracer.omwaddon
content=hub_annex.omwaddon
```

### Required settings.cfg entries for the Game Template

The example suite ships a `settings.cfg` with required `[Models]` overrides that
redirect the engine away from the classic Morrowind NIF animations to the `.dae`
files used by the template. **Do not copy the file wholesale** — manually add the
sections to your existing `~/.config/openmw/settings.cfg` as documented at
https://openmw.readthedocs.io/en/stable/reference/modding/openmw-game-template.html

Without these entries OpenMW will crash on new-game with:
`Failed to start a new game: Resource 'meshes/base_anim.nif' not found`

```ini
[Models]
xbaseanim           = meshes/BasicPlayer.dae
baseanim            = meshes/BasicPlayer.dae
xbaseanim1st        = meshes/BasicPlayer.dae
baseanimkna         = meshes/BasicPlayer.dae
baseanimkna1st      = meshes/BasicPlayer.dae
xbaseanimfemale     = meshes/BasicPlayer.dae
baseanimfemale      = meshes/BasicPlayer.dae
baseanimfemale1st   = meshes/BasicPlayer.dae
xargonianswimkna    = meshes/BasicPlayer.dae
xbaseanimkf         = meshes/BasicPlayer.dae
xbaseanim1stkf      = meshes/BasicPlayer.dae
xbaseanimfemalekf   = meshes/BasicPlayer.dae
xargonianswimknakf  = meshes/BasicPlayer.dae
skyatmosphere       = meshes/sky_atmosphere.dae
skyclouds           = meshes/sky_clouds_01.osgt
skynight01          = meshes/sky_night_01.osgt

[Game]
default actor pathfind half extents = 15.656299591064453125 15.656299591064453125 69.1493988037109375
```

---

## 10. Recipes

### Add a global variable

```python
addon.add_global("MyMod_Enabled", type="short", value=1)
```

### Create a vendor NPC

```python
addon.add_npc(
    id="mymod_vendor_01",
    name="Merchant Name",
    race="Breton",
    npc_class="Merchant",
    disposition=60,
    gold=500,
    flags=["autocalc"],
    services=0x0004,  # barter
    inventory=[("iron longsword", 2), ("bread", 10)],
)
```

### Create an interior cell and furnish it

```python
cell = addon.add_interior_cell("My Shop", flags=["illegal_to_sleep"])
cell.place_npc("mymod_vendor_01", x=0, y=128, z=0)
cell.place_container("mymod_chest_01", x=200, y=0, z=0)
cell.place_light("mymod_torch_01", x=0, y=0, z=180)
```

### Create a door connecting two cells

```python
# In cell A:
cell_a.place_door(
    "door_a_to_b",
    x=0, y=-300, z=0,
    destination_cell="Cell B Name",
    destination_pos=(0, 150, 0),
)
# In cell B:
cell_b.place_door(
    "door_b_to_a",
    x=0, y=150, z=0,
    destination_cell="Cell A Name",
    destination_pos=(0, -280, 0),
)
```

### Add a spell

```python
addon.add_spell(
    id="mymod_fire_bolt",
    name="Fire Bolt",
    cost=12,
    effects=[{
        "effect_id": 14,  # Fireball
        "range": 2,       # 2 = target
        "duration": 1,
        "magnitude_min": 10,
        "magnitude_max": 20,
    }],
)
```

### Add a book with readable text

```python
addon.add_book(
    id="mymod_tome_01",
    name="The Secret Tome",
    text="<DIV ALIGN=CENTER><FONT SIZE=4>The Secret Tome</FONT></DIV><BR>...",
    weight=1.5,
    value=200,
)
```

### Attach MWScript to an NPC

```python
addon.add_script(
    id="mymod_guard_script",
    source="Begin mymod_guard_script\n; script body\nEnd",
)
addon.add_npc(
    id="mymod_guard_01",
    # ...
    script="mymod_guard_script",
)
```

### Create a levelled item list

```python
addon.add_levelled_list(
    id="mymod_chest_loot",
    items=[
        ("iron dagger", 1),        # spawns at PC level ≥ 1
        ("silver dagger", 5),      # spawns at PC level ≥ 5
        ("ebony dagger", 15),      # spawns at PC level ≥ 15
    ],
    chance_none=15,
    flags=0x01,  # pick from all eligible levels
)
```

### Override a game setting

```python
addon.add_game_setting("fJumpHeightMin", 60.0)
addon.add_game_setting("iVoiceGenderChange", 1)
addon.add_game_setting("sLevelUpMsg", "You grew stronger!")
```

### Write a GLOBAL Lua script with a timer

```lua
-- scripts/mymod/global.lua
local async = require('openmw.async')

local function onInit()
    async:newTimerInRealSeconds(5, function()
        print("[MyMod] 5 seconds have passed.")
    end)
end

return { engineHandlers = { onInit = onInit } }
```

### Send events between Global and Local scripts

```lua
-- Global script
local core = require('openmw.core')

core.sendGlobalEvent("MyMod_Ping", { data = 42 })

local function onGlobalEvent(name, data)
    if name == "MyMod_Pong" then
        print("Got pong:", data.data)
    end
end

return { eventHandlers = { MyMod_Pong = onGlobalEvent } }

-- Local script (on NPC)
local self_module = require('openmw.self')

local function onMyModPing(data)
    self_module.sendGlobalEvent("MyMod_Pong", { data = data.data + 1 })
end

return { eventHandlers = { MyMod_Ping = onMyModPing } }
```

### Persist data across saves

```lua
local storage = require('openmw.storage')
local section = storage.globalSection("MyMod_State")

local function onSave()
    section:set("myValue", 42)
end

local function onLoad()
    local v = section:get("myValue")
end
```

---

## 11. Gotchas

- **IDs are case-insensitive** in the engine. Always use lowercase in new content.
- **Strings are null-terminated** (`\x00` at end). The reader strips them; the
  writer adds them automatically.
- **Interior CELLs** use `NAME` as their identifier. Exterior cells use
  `(grid_x, grid_y)` from `CELL/DATA`. Interior flag (0x01) must be set.
- **NPC_ autocalc**: when the `0x0008` flag is set, the engine ignores explicit
  stats in `NPDT`. Use the 12-byte short form of `NPDT`.
- **MAST/DATA pairs**: the file size in `DATA` is checked by some tools but
  OpenMW only warns on mismatch (not a hard error). Pass 0 if unknown.
- **DIAL/INFO ordering**: `INFO` records form a linked list via `PNAM`/`NNAM`.
  They must appear in the file after their parent `DIAL`. Order matters.
- **Lua scripts are NOT inside the binary**: they live as loose files in a
  `data` directory. The addon only needs the `.omwscripts` manifest.
- **SCDT bytecode is optional in OpenMW**: source-only (`SCTX`) scripts are
  compiled on load. For distribution include bytecode if possible.
- **`MODL` / `ITEX` paths** are VFS-relative, e.g. `meshes/x/myobj.nif` or
  `icons/m/my_icon.dds`. They are looked up across all registered `data=` dirs.
- **Hot-reload Lua**: use `reloadlua` in the OpenMW in-game console. Only works
  for loose files (not packed inside a `.omwaddon`).

### Confirmed OpenMW loader hard errors (discovered via live testing)

These will crash OpenMW at load with a fatal ESM error; not just warnings:

- **`CELL/DATA` must be exactly 12 bytes** — `struct.pack("<Iii", flags, grid_x, grid_y)`.
  Both interior and exterior cells. Writing 16 bytes (`<IIii`) causes:
  `ESM Error: record size mismatch, requested 12, got 16 — Record: CELL Subrecord: DATA`

- **`CONT/FLAG` bit 3 (0x08) must always be set** — even for plain non-organic,
  non-respawning containers. The builder defaults to `0x08`. Omitting it causes:
  `ESM Error: Flag 8 not set — Record: CONT Subrecord: FLAG`
  (All vanilla Morrowind containers have this bit set; the engine enforces it.)

- **`CELL/DATA` tag is overloaded**: 12-byte payload = cell header (`<Iii`);
  24-byte payload = object reference position (`<ffffff` = x, y, z, rot_x, rot_y, rot_z).
  The reader dispatches by size. The position order is position-first, rotation-second.

### Known non-fatal example suite warnings

These warnings appear in the OpenMW log when running the example suite (including
`hub_annex`). They are **pre-existing limitations of the example suite itself**,
not bugs introduced by this toolkit. Do not attempt to fix them.

| Warning | Source | Reason |
|---------|--------|--------|
| `Can't find texture: textures/menu_small_energy_bar_*.dds` | engine UI | Example suite never ships HUD textures |
| `nif load failed: meshes/ashcloud.nif` (and blightcloud, snow, blizzard) | weather system | No weather meshes in the template |
| `Can't find texture: textures/hu_male.dds` | `BasicPlayer.dae` | Referenced in the DAE but never committed to the repo |
| `Cell reference 'raceryo' not found` | `the_hub.omwaddon` | Pre-existing reference to a removed/renamed object |
| `LandRacer: bind_material not found for geometry CHANNEL1` | `landracer.omwaddon` mesh | DAE material binding issue in the upstream asset |
| `LandRacer: no bone … in skeleton` | `landracer.omwaddon` mesh | Bone names in the DAE don't match skeleton expectations |

---

## 12. Extending the Toolkit

### Adding a new record type

1. Add subrecord schemas to `tes3/schema.py` — one `SubrecordSchema`,
   `StringSchema`, or `HedrSchema` per `(RECORD_TAG, SUBREC_TAG)` key.
2. Add a builder method `add_<type>()` in `addon/builder.py`.
3. Optionally add a sub-builder in `addon/types/<type>.py`.

### Adding 3D mesh / texture support

The toolkit is designed to be extended with mesh and texture support:

- `tes3/schema.py` already marks asset-path subrecords in `ASSET_PATH_SUBRECORDS`:
  - `MODL` → mesh (.nif)
  - `ITEX` / `ICON` → icon texture (.dds/.tga)
  - `PTEX` → particle texture
- A future `tes3mesh` subpackage would parse/write NIF files using the VFS
  path stored in `MODL` subrecords.
- A future `tes3tex` subpackage would handle DDS/TGA textures from `ITEX`.
- The `addon/builder.py` methods already accept `mesh=` and `icon=` parameters
  that write `MODL`/`ITEX` subrecords with the given VFS path.

```python
# When tes3mesh is available:
# from tes3mesh import read_nif, write_nif
# mesh = read_nif("data/meshes/x/myobj.nif")
# mesh.modify(...)
# write_nif(mesh, "data/meshes/x/myobj_modified.nif")
```

### Running tests

```bash
poetry run pytest tests/ -v
```

The round-trip tests verify that all four example-suite files parse and
re-serialize to bit-identical output.
