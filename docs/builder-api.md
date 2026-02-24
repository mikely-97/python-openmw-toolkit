# Builder API & Low-Level API

## Builder API — `addon/builder.py`

```python
from addon import AddonBuilder

addon = AddonBuilder(
    description="My addon",
    company="My Studio",
    masters=["template.omwgame"],   # or list of (name, size) tuples
    file_type=0,                    # 0=addon, 1=master
)

addon.add_global("MyMod_Version", type="short", value=1)
# type: 'short'|'long'|'float'  (or 's'|'l'|'f')

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
    mesh="",                # blank = use race default
)

addon.add_static("mymod_pillar_01", mesh="x/mymod_pillar.nif")
# MODL paths omit leading "meshes/" — engine adds it

addon.add_light(
    id="mymod_candle_01",
    radius=100,
    color=(255, 200, 120),
    flags=["dynamic", "fire", "can_carry"],
    duration=3600,
)

addon.add_container(
    id="mymod_chest_01",
    name="Old Chest",
    capacity=200.0,
    inventory=[("Gold_001", 50)],
)

addon.add_misc_item(id="mymod_key_01", name="Rusty Key", weight=0.1, value=5)

addon.add_book(
    id="mymod_tome_01",
    name="Tome of Secrets",
    text="<DIV ALIGN=CENTER>The secrets are...</DIV>",
    weight=2.0,
    value=100,
)

# spell_type: 0=spell, 1=ability, 2=blight, 3=disease, 4=curse, 5=power
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

addon.add_game_setting("fJumpHeightMin", 50.0)
addon.add_game_setting("iNumberCreaturesAttackMe", 3)
addon.add_game_setting("sLevelUpMsg", "You levelled up!")

addon.add_levelled_list(
    id="mymod_random_loot",
    items=[("iron dagger", 1), ("gold_005", 1)],
    chance_none=10,
    flags=0x01,     # 0x01=calc from all levels <= PC, 0x02=calc for each item
)

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
    ambient=0x404040FF,     # 0xRRGGBBAA — builder unpacks to bytes
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

# Escape hatch: append a raw record dict
addon.append_raw_record({
    "tag": "GMST",
    "flags": 0,
    "hdr1": 0,
    "subrecords": [
        {"tag": "NAME", "raw": b"sLevelUpMsg\x00"},
        {"tag": "STRV", "raw": b"Level up!\x00"},
    ],
})

addon.save("mymod.omwaddon")
data: bytes = addon.to_bytes()
```

## Low-Level API — `tes3/reader.py` and `tes3/writer.py`

```python
from tes3.reader import read_file, read_bytes
from tes3.writer import write_file, write_bytes

records = read_file("file.omwaddon")

# Record dict structure:
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

for rec in records:
    if rec["tag"] == "GLOB":
        for sr in rec["subrecords"]:
            if sr["tag"] == "FLTV":
                import struct
                sr["raw"] = struct.pack("<f", 99.0)

write_file(records, "modified.omwaddon")
# Round-trip is bit-identical (writer always uses "raw" bytes)
```

## Extending the Toolkit

### Adding a new record type

1. Add subrecord schemas to `tes3/schema.py` — one `SubrecordSchema`, `StringSchema`, or `HedrSchema` per `(RECORD_TAG, SUBREC_TAG)` key.
2. Add a builder method `add_<type>()` in `addon/builder.py`.
3. Optionally add a sub-builder in `addon/types/<type>.py`.

### Adding 3D mesh / texture support

`tes3/schema.py` marks asset-path subrecords in `ASSET_PATH_SUBRECORDS`:
- `MODL` → mesh (.nif)
- `ITEX` / `ICON` → icon texture (.dds/.tga)
- `PTEX` → particle texture

The `addon/builder.py` methods already accept `mesh=` and `icon=` parameters that write `MODL`/`ITEX` subrecords with the given VFS path.

## Recipes

### Vendor NPC

```python
addon.add_npc(
    id="mymod_vendor_01",
    name="Merchant Name",
    race="Breton",
    npc_class="Merchant",
    disposition=60,
    gold=500,
    flags=["autocalc"],
    services=0x0004,  # barter; 0x2511 = general goods + weapons + apparatus + misc + potions
    inventory=[("iron longsword", 2), ("bread", 10)],
)
```

### Interior cell with door

```python
cell = addon.add_interior_cell("My Shop", flags=["illegal_to_sleep"])
cell.place_npc("mymod_vendor_01", x=0, y=128, z=0)
cell.place_container("mymod_chest_01", x=200, y=0, z=0)
cell.place_light("mymod_torch_01", x=0, y=0, z=180)
cell.place_door("door_a_to_b", x=0, y=-300, z=0,
                destination_cell="Cell B Name", destination_pos=(0, 150, 0))
```

### Levelled loot list

```python
addon.add_levelled_list(
    id="mymod_chest_loot",
    items=[("iron dagger", 1), ("silver dagger", 5), ("ebony dagger", 15)],
    chance_none=15,
    flags=0x01,
)
```

### Override EnableMenus for custom spawn

```python
addon.add_script(
    id="EnableMenus",   # replaces template's version (loads last)
    source=(
        "Begin EnableMenus\n"
        "EnableMagicMenu\nEnableInventoryMenu\nEnableMapMenu\n"
        "EnableStatsMenu\nEnableRest\n"
        "set CharGenState to -1\n"
        'Player->PositionCell 0, -300, 0, 0, "YourCellName"\n'
        "stopscript EnableMenus\n"
        "End EnableMenus\n"
    ),
)
```

### Running tests

```bash
poetry run pytest tests/ -v
```
