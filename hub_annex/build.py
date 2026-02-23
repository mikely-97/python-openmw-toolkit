"""hub_annex — "The Watchman's Post"

A small addon for the OpenMW example suite that adds:
  - An exterior watch-tower building east of the main hub entry arch
  - A door from the exterior into a new interior cell
  - A Land Racer creature patrolling outside
  - An interior cell with room geometry, lights, and a chest

Masters required (load order):
  1. template.omwgame
  2. the_hub.omwaddon
  3. landracer.omwaddon

Use the Flatpak release of OpenMW (system package has incompatible osgdb_dae.so):
  flatpak run --command=openmw org.openmw.OpenMW

Add to ~/.var/app/org.openmw.OpenMW/config/openmw/openmw.cfg:
  data="<path>/example-suite/game_template/data"
  data="<path>/example-suite/the_hub/data"
  data="<path>/example-suite/example_animated_creature/data"
  data="<path>/example-suite"          # hub_annex.omwaddon lives at suite root
  content=template.omwgame
  content=the_hub.omwaddon
  content=landracer.omwaddon
  content=hub_annex.omwaddon

Also required — add to ~/.var/app/org.openmw.OpenMW/config/openmw/settings.cfg
(do NOT overwrite the file; add these sections manually per the wiki):
  https://openmw.readthedocs.io/en/stable/reference/modding/openmw-game-template.html
  [Models] section with BasicPlayer.dae remaps
  [Game] section with pathfind half extents

The build script writes directly to <path>/example-suite/hub_annex.omwaddon.

Usage:
  poetry run python hub_annex/build.py
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from addon import AddonBuilder
from addon.types.cell import _next_frmr

# ---------------------------------------------------------------------------
# Master file sizes (exact bytes — OpenMW warns but continues on mismatch)
# ---------------------------------------------------------------------------
MASTERS = [
    ("template.omwgame",   150647),
    ("the_hub.omwaddon",   815804),
    ("landracer.omwaddon",   1281),
]

# ---------------------------------------------------------------------------
# Exterior placement — all inside the Hub Islands exterior cell (grid 0, 0).
# The hub's main structure is around (4000–6300, 4037, 300–900).
# We place the annex east of the entry arch, on the same plateau.
# ---------------------------------------------------------------------------
#
# Existing landmarks for reference:
#   HubEnv_EntryArch  (6150, 4037, 815)
#   HubEnv_SmallTower (5937, 4037, 300)
#   HubEnv_RoundPlate (6265, 4037, 864)   ← the top hub platform
#
# Our new objects:
TOWER_POS    = (7100.0, 4100.0, 300.0)   # small watchtower building
DOOR_EXT_POS = (7000.0, 3950.0, 300.0)   # exterior door into the annex
CREATURE_POS = (6700.0, 3600.0, 300.0)   # land racer patrolling

# Interior door destination (inside "The Watchman's Post")
DOOR_INT_POS = (0.0, -500.0, 10.0)       # just inside the interior door

# ---------------------------------------------------------------------------
# Helper: raw object-reference DATA subrecord (x, y, z, rx, ry, rz)
# ---------------------------------------------------------------------------
def _ref_data(x, y, z, rx=0.0, ry=0.0, rz=0.0) -> dict:
    return {"tag": "DATA", "raw": struct.pack("<ffffff", x, y, z, rx, ry, rz)}

def _str(tag: str, value: str) -> dict:
    return {"tag": tag, "raw": value.encode("latin-1") + b"\x00", "parsed": value}

def _raw(tag: str, data: bytes) -> dict:
    return {"tag": tag, "raw": data}

# ---------------------------------------------------------------------------
# Build the addon
# ---------------------------------------------------------------------------
addon = AddonBuilder(
    description="The Watchman's Post - a small annex east of the Hub entry arch",
    company="Example",
    masters=MASTERS,
)

# ---- Define a new DOOR record reusing an existing hub door mesh -----------
# (the mesh doors/hubtemple_doors01.dae is already in the VFS from the_hub)
addon.append_raw_record({
    "tag": "DOOR",
    "flags": 0, "hdr1": 0,
    "subrecords": [
        _str("NAME", "hub_annex_door"),
        _str("MODL", "doors/hubtemple_doors01.dae"),
        _str("FNAM", "Annex Door"),
    ],
})

# ---- Interior cell: "The Watchman's Post" ---------------------------------
# Room geometry uses existing hub temple mesh assets from the_hub VFS.
cell = addon.add_interior_cell(
    "The Watchman's Post",
    ambient=0x303050FF,
    sunlight=0x000000FF,
    fog_color=0x202030FF,
    fog_density=0.4,
)

# Main room shell
cell.place_static("HubTemple_StartingRoom", x=0, y=0, z=0)

# Pillars at the four corners
for px, py in [(220, 220), (-220, 220), (220, -220), (-220, -220)]:
    cell.place_static("HubTemple_Pillar01", x=px, y=py, z=0)

# Lights — two wall sconces
cell.place_light("HubEnv_BasicLight", x=180, y=0, z=220)
cell.place_light("HubEnv_BasicLight", x=-180, y=0, z=220)

# A chest with some weapons for the watchman
addon.add_container(
    id="hub_annex_chest",
    name="Watchman's Chest",
    mesh="containers/hub_chest01.dae",
    capacity=200.0,
    inventory=[
        ("Basic_Sword1h", 1),
        ("Basic_Dagger1h", 1),
    ],
)
cell.place_container("hub_annex_chest", x=280, y=-100, z=0)

# A weapon rack against the back wall
cell.place_static("Hub_WeaponStand01", x=0, y=280, z=0, rot_z=3.14159)

# A book with a note from the watchman
addon.add_book(
    id="hub_annex_note",
    name="Watchman's Log",
    weight=0.2,
    value=5,
    text=(
        "<DIV ALIGN=CENTER><FONT SIZE=4>Watchman's Log</FONT></DIV>"
        "<BR>"
        "<BR>Day 1: Posted at the east tower. The land racers are restless today."
        "<BR>"
        "<BR>Day 3: One racer came within ten feet of the door. I've reinforced the lock."
        "<BR>"
        "<BR>Day 7: The hub council says the creatures are harmless. They clearly have "
        "not stood watch out here at night."
    ),
)
cell.place_item("hub_annex_note", x=-100, y=100, z=5)

# Interior side of the door — leads back to exterior cell (0,0)
# Place the interior door — append raw subrecords directly to the cell record
# We do this by appending raw subrecords to the cell's record dict directly.
frmr_val = _next_frmr()
interior_door_subrecords = [
    _raw("FRMR", struct.pack("<I", frmr_val)),
    _str("NAME", "hub_annex_door"),
    # Destination: back to exterior cell at the exterior door coords
    _raw("DODT", struct.pack("<ffffff",
         DOOR_EXT_POS[0], DOOR_EXT_POS[1], DOOR_EXT_POS[2] + 50,
         0.0, 0.0, 0.0)),
    _str("DNAM", ""),  # empty = exterior cell
    _ref_data(0.0, -460.0, 0.0, rz=3.14159),   # face outward
]
cell._record["subrecords"].extend(interior_door_subrecords)

# ---- Exterior cell additions — Hub Islands (grid 0, 0) --------------------
# We add a new CELL record at grid (0,0). The engine merges object refs.
# FRMR values: we use 200+ to avoid all existing FRMRs (hub uses 0-6,
# landracer uses 11-16, raceryo override uses 0x01xxxxxx range).

ext_subrecords = [
    _str("NAME", "Hub Islands"),
    # 12-byte CELL DATA: flags(I) + grid_x(i) + grid_y(i)
    _raw("DATA", struct.pack("<Iii", 0, 0, 0)),
    _str("RGNN", "TheHub"),
]

def _place_ext(base_id, x, y, z, rx=0.0, ry=0.0, rz=0.0, frmr=None):
    """Append an exterior object reference to ext_subrecords."""
    global _ext_frmr
    f = frmr if frmr is not None else _ext_frmr
    if frmr is None:
        _ext_frmr += 1
    ext_subrecords.extend([
        _raw("FRMR", struct.pack("<I", f)),
        _str("NAME", base_id),
        _ref_data(x, y, z, rx, ry, rz),
    ])

_ext_frmr = 200

# The watchtower building exterior (HubEnv_SmallTower is defined in the_hub.omwaddon)
_place_ext("HubEnv_SmallTower",
           TOWER_POS[0], TOWER_POS[1], TOWER_POS[2])

# The exterior door (with teleport destination into the interior)
_place_ext("hub_annex_door",
           DOOR_EXT_POS[0], DOOR_EXT_POS[1], DOOR_EXT_POS[2],
           rz=1.5708)   # 90° so door faces west toward the hub

# Insert DODT + DNAM after the door's DATA
ext_subrecords.extend([
    _raw("DODT", struct.pack("<ffffff",
         DOOR_INT_POS[0], DOOR_INT_POS[1], DOOR_INT_POS[2],
         0.0, 0.0, 0.0)),
    _str("DNAM", "The Watchman's Post"),
])

# The Land Racer creature patrolling outside
_place_ext("LandRacer",
           CREATURE_POS[0], CREATURE_POS[1], CREATURE_POS[2])

addon.append_raw_record({
    "tag": "CELL",
    "flags": 0, "hdr1": 0,
    "subrecords": ext_subrecords,
})

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out_dir = Path("/home/mike/Documents/Games/Morrowind_OpenMW_Linux/game/example-suite")
out = out_dir / "hub_annex.omwaddon"
addon.save(out)
print(f"Written: {out}")

# Quick sanity check
from tes3.reader import read_file
from tools.validate import validate
recs = read_file(out)
result = validate(recs)
for e in result.errors:
    print(f"ERROR   {e}")
for w in result.warnings:
    print(f"WARNING {w}")
if result.ok:
    print(f"Validated OK — {len(recs)} records")
