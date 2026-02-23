"""hub_world/build.py — The Hub World addon.

A self-contained progression zone with four interior cells:

  Hub World   — main lobby: vendor, bed, anvil, forge, three doors
  Hub Garden  — pick herbs/flowers (respawn 24 h); open from start
  Hub Forest  — chop trees (Axe skill, respawn 7 days), pick mushrooms
                (24 h); requires Forest Pass bought from vendor
  Hub Mine    — mine iron ore / stone (Blunt skill, no auto-respawn;
                buy Mine Refresh from vendor); requires Mine Pass

Gameplay loop
-------------
1. Start in Hub World. Vendor sells basic tools and passes.
2. Garden: gather herbs → use alchemy apparatus to brew Restore Health /
   Restore Fatigue potions → sell or drink.
3. Forest (buy pass): chop trees for logs/branches.  At the Anvil craft
   wooden axes (Repair skill) and other instruments.
4. Mine (buy pass): use pickaxe → iron ore → smelt at Forge → iron ingots
   → craft iron tools at Anvil → sell or keep.

Meshes
------
All mesh paths point to `meshes/hub_world/<name>.dae`.  Run
`generate_meshes.py` inside Blender to create the placeholder geometry, or
replace the paths with existing VFS assets.

Run
---
    cd hub_world/
    poetry run python build.py
    # → hub_world.omwaddon

Then in openmw.cfg:
    data="path/to/hub_world/data"
    content=hub_world.omwaddon
    content=hub_world.omwscripts
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from addon import AddonBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

M = "hub_world/"   # mesh namespace — engine prepends "meshes/" automatically


def mesh(name: str) -> str:
    """Return VFS-relative mesh path."""
    return M + name + ".dae"


def icon(name: str) -> str:
    return "icons/hub_world/" + name + ".dds"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

addon = AddonBuilder(
    description="Hub World - a progression training zone.\n"
                "Four cells: Hub, Garden, Forest, Mine.",
    company="HubWorld",
    masters=["template.omwgame"],
    file_type=0,
)

addon.add_global("hw_version", type="short", value=1)

# Override the starting cell so new games begin in our lobby.
# hub_world.omwaddon loads last in the content list, so this GMST takes
# precedence over template.omwgame's "Place of Initialization".
addon.add_game_setting("sStartCell", "IdleMW")

# ===========================================================================
# ITEMS
# ===========================================================================

# -- Ingredients (harvestable plants / mushrooms) ---------------------------
# effect_id 75 = Restore Health,  77 = Restore Fatigue  (Morrowind IDs)
RESTORE_HEALTH = {"effect_id": 75, "skill_id": -1, "attribute_id": -1}
RESTORE_FATIGUE = {"effect_id": 77, "skill_id": -1, "attribute_id": -1}

addon.add_ingredient("hw_herb_basil",
    name="Garden Basil", mesh=mesh("plant_herb"),
    weight=0.1, value=5,
    effects=[RESTORE_HEALTH])

addon.add_ingredient("hw_herb_mint",
    name="Garden Mint", mesh=mesh("plant_herb"),
    weight=0.1, value=5,
    effects=[RESTORE_FATIGUE])

addon.add_ingredient("hw_mushroom_heal",
    name="Healing Mushroom", mesh=mesh("plant_mushroom"),
    weight=0.2, value=12,
    effects=[RESTORE_HEALTH, RESTORE_HEALTH])   # two RH effects = stronger potion

addon.add_ingredient("hw_mushroom_vigor",
    name="Vigor Mushroom", mesh=mesh("plant_mushroom"),
    weight=0.2, value=12,
    effects=[RESTORE_FATIGUE, RESTORE_FATIGUE])

# -- Raw materials (misc items) ---------------------------------------------
addon.add_misc_item("hw_log",    name="Wooden Log",     mesh=mesh("log"),    weight=4.0, value=3)
addon.add_misc_item("hw_branch", name="Branch",          mesh=mesh("branch"), weight=1.0, value=1)
addon.add_misc_item("hw_iron_ore",    name="Iron Ore",   mesh=mesh("mineral_iron"), weight=3.0, value=8)
addon.add_misc_item("hw_iron_ingot",  name="Iron Ingot", mesh=mesh("ingot"),        weight=2.0, value=20)
addon.add_misc_item("hw_stone",       name="Stone Chunk",mesh=mesh("mineral_stone"),weight=2.0, value=2)
addon.add_misc_item("hw_instrument_wood",
    name="Wooden Instrument", mesh=mesh("instrument"),
    weight=1.5, value=40)

# -- Access tokens (pass items, key=True equivalent — no lock consumption) --
# These are MISC items with no special flag; locked doors check for them
# via Lua scripts rather than engine key mechanics.
addon.add_misc_item("hw_forest_pass",
    name="Forest Pass", mesh=mesh("pass_token"),
    weight=0.0, value=150)

addon.add_misc_item("hw_mine_pass",
    name="Mine Pass", mesh=mesh("pass_token"),
    weight=0.0, value=400)

addon.add_misc_item("hw_mine_refresh",
    name="Mine Refresh Token", mesh=mesh("pass_token"),
    weight=0.0, value=250)

# -- Weapons ----------------------------------------------------------------
# Wooden Axe  — starter axe, Axe 1H (type 6), low damage + durability
addon.add_weapon("hw_axe_wooden",
    name="Wooden Axe", mesh=mesh("axe_wooden"),
    weight=2.0, value=10,
    type_id=6, health=50, speed=1.1, reach=1.0,
    chop_min=2, chop_max=7, slash_min=1, slash_max=5, thrust_min=1, thrust_max=3)

# Iron Axe — better tree-chopper
addon.add_weapon("hw_axe_iron",
    name="Iron Axe", mesh=mesh("axe_iron"),
    weight=6.0, value=100,
    type_id=6, health=250, speed=0.8, reach=1.1,
    chop_min=5, chop_max=16, slash_min=3, slash_max=12, thrust_min=1, thrust_max=5)

# Crafted Wooden Axe — better than hw_axe_wooden, produced at Anvil
addon.add_weapon("hw_axe_wooden_craft",
    name="Crafted Wooden Axe", mesh=mesh("axe_wooden"),
    weight=2.5, value=25,
    type_id=6, health=90, speed=1.0, reach=1.05,
    chop_min=4, chop_max=11, slash_min=2, slash_max=8, thrust_min=1, thrust_max=4)

# Basic Pickaxe — Blunt 1H (type 3), for mining
addon.add_weapon("hw_pickaxe_basic",
    name="Basic Pickaxe", mesh=mesh("pickaxe_basic"),
    weight=3.0, value=15,
    type_id=3, health=80, speed=0.9, reach=1.0,
    chop_min=1, chop_max=4, slash_min=1, slash_max=4, thrust_min=2, thrust_max=8)

# Iron Pickaxe — better miner, crafted at Anvil (3 ingots)
addon.add_weapon("hw_pickaxe_iron",
    name="Iron Pickaxe", mesh=mesh("pickaxe_iron"),
    weight=8.0, value=120,
    type_id=3, health=300, speed=0.7, reach=1.0,
    chop_min=2, chop_max=8, slash_min=2, slash_max=7, thrust_min=5, thrust_max=18)

# -- Alchemy apparatus ------------------------------------------------------
# type: 0=Mortar&Pestle, 1=Alembic, 2=Calcinator, 3=Retort
addon.add_apparatus("hw_mortar_basic",
    name="Basic Mortar & Pestle", mesh=mesh("apparatus_mortar"),
    apparatus_type=0, quality=0.4, weight=3.0, value=30)

addon.add_apparatus("hw_alembic_basic",
    name="Basic Alembic", mesh=mesh("apparatus_alembic"),
    apparatus_type=1, quality=0.4, weight=2.0, value=60)

addon.add_apparatus("hw_calcinator_basic",
    name="Basic Calcinator", mesh=mesh("apparatus_calcinator"),
    apparatus_type=2, quality=0.4, weight=5.0, value=80)

addon.add_apparatus("hw_retort_basic",
    name="Basic Retort", mesh=mesh("apparatus_retort"),
    apparatus_type=3, quality=0.4, weight=4.0, value=70)

# ===========================================================================
# ACTIVATORS (harvestable world objects + interactive stations)
# ===========================================================================

# -- Garden plants (10 individual instances, each a separate record) --------
for i in range(1, 6):
    addon.add_activator(f"hw_plant_basil_{i:02d}",
        name="Garden Basil", mesh=mesh("plant_herb"))
    addon.add_activator(f"hw_plant_mint_{i:02d}",
        name="Garden Mint", mesh=mesh("plant_herb"))

# -- Forest mushrooms (8 instances) -----------------------------------------
for i in range(1, 5):
    addon.add_activator(f"hw_mushroom_heal_{i:02d}",
        name="Healing Mushroom", mesh=mesh("plant_mushroom"))
    addon.add_activator(f"hw_mushroom_vigor_{i:02d}",
        name="Vigor Mushroom", mesh=mesh("plant_mushroom"))

# -- Forest trees (6 instances) ---------------------------------------------
for i in range(1, 7):
    addon.add_activator(f"hw_tree_{i:02d}",
        name="Tree", mesh=mesh("tree"))

# -- Mine minerals ----------------------------------------------------------
for i in range(1, 9):
    addon.add_activator(f"hw_mineral_iron_{i:02d}",
        name="Iron Deposit", mesh=mesh("mineral_iron"))
for i in range(1, 5):
    addon.add_activator(f"hw_mineral_stone_{i:02d}",
        name="Stone Deposit", mesh=mesh("mineral_stone"))

# -- Hub stations -----------------------------------------------------------
addon.add_activator("hw_bed",          name="Bed",                mesh=mesh("bed"))
addon.add_activator("hw_anvil",        name="Anvil",              mesh=mesh("anvil"))
addon.add_activator("hw_forge",        name="Forge",              mesh=mesh("forge"))
addon.add_activator("hw_mine_refresh_station",
    name="Mine Management Board",      mesh=mesh("mine_refresh"))

# -- Garden door: real DOOR record — engine handles teleportation natively.
addon.add_door_record("hw_door_garden",
    name="Garden [Open]",      mesh=mesh("door_green"))
addon.add_door_record("hw_door_return_garden",
    name="Return to Hub",      mesh=mesh("door_gray"))

# -- Forest/Mine doors: ACTI — Lua checks pass before teleporting.
addon.add_activator("hw_door_forest",
    name="Forest [Forest Pass needed]", mesh=mesh("door_brown"))
addon.add_activator("hw_door_mine",
    name="Mine [Mine Pass needed]",     mesh=mesh("door_gray"))
addon.add_activator("hw_door_return_forest",
    name="Return to Hub",               mesh=mesh("door_gray"))
addon.add_activator("hw_door_return_mine",
    name="Return to Hub",               mesh=mesh("door_gray"))

# ===========================================================================
# VENDOR NPC
# ===========================================================================
# Services bits: 0x0001=Weapon, 0x0010=Ingredient, 0x0100=Apparatus,
#                0x0400=Misc, 0x2000=Potions
# Combined 0x2511 = general goods + weapons + apparatus + misc + potions

addon.add_npc(
    id="hw_vendor",
    name="The Vending Machine",
    race="DefaultRace",
    npc_class="DefaultClass",
    faction="",
    mesh="basicplayer.dae",   # game-template skeleton mesh; NPC must have this to be clickable
    disposition=70,
    level=10,
    gold=2000,
    flags=["autocalc"],
    services=0x2511,
    inventory=[
        # Passes
        ("hw_forest_pass",   20),
        ("hw_mine_pass",     10),
        ("hw_mine_refresh",  20),
        # Weapons
        ("hw_axe_wooden",     5),
        ("hw_axe_iron",       3),
        ("hw_pickaxe_basic",  5),
        ("hw_pickaxe_iron",   3),
        # Apparatus
        ("hw_mortar_basic",   3),
        ("hw_alembic_basic",  3),
        ("hw_calcinator_basic", 2),
        ("hw_retort_basic",   2),
    ],
)

# ===========================================================================
# LIGHTS (reused across cells)
# ===========================================================================

addon.add_light("hw_light_ceiling",
    name="", radius=700, color=(255, 255, 255),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic"])

# Corner fill lights — neutral white so they don't tint materials
addon.add_light("hw_light_fill",
    name="", radius=400, color=(240, 245, 255),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic"])

# Forge glow — warm orange, only used near the forge
addon.add_light("hw_light_forge_glow",
    name="", radius=200, color=(255, 140, 40),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic", "fire", "flicker"])

addon.add_light("hw_light_garden",
    name="", radius=600, color=(255, 255, 255),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic"])

addon.add_light("hw_light_forest",
    name="", radius=500, color=(255, 255, 255),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic"])

addon.add_light("hw_light_mine",
    name="", radius=280, color=(255, 210, 130),
    duration=-1, weight=0.0, value=0,
    flags=["dynamic", "fire", "flicker"])

# ===========================================================================
# STATIC DECORATION
# ===========================================================================

# Decorative pillars for Hub World
addon.add_static("hw_pillar",          mesh=mesh("pillar"))
# Floor panels (large flat planes to define room boundaries visually)
addon.add_static("hw_floor_hub",       mesh=mesh("floor_hub"))
addon.add_static("hw_floor_garden",    mesh=mesh("floor_garden"))
addon.add_static("hw_floor_forest",    mesh=mesh("floor_forest"))
addon.add_static("hw_floor_mine",      mesh=mesh("floor_mine"))
# Wall panels — N/S (long in X) and E/W (long in Y, no rotation needed)
addon.add_static("hw_wall_hub",        mesh=mesh("wall_hub"))
addon.add_static("hw_wall_small",      mesh=mesh("wall_small"))
addon.add_static("hw_wall_hub_ew",     mesh=mesh("wall_hub_ew"))
addon.add_static("hw_wall_small_ew",   mesh=mesh("wall_small_ew"))
# Vending machine chassis — purely decorative STAT
addon.add_static("hw_vending_machine", mesh=mesh("vending_machine"))


# ===========================================================================
# DIALOGUE — greetings and flavor topics for the vending machine NPC
# ===========================================================================

# Greeting (type=2): shown automatically when the player activates the NPC
addon.add_dialogue_topic(
    name="Greetings",
    topic_type=2,
    responses=[{
        "id": "hw_greet_001",
        "prev_id": "",
        "next_id": "",
        "text": "Welcome to the Hub. I stock tools, passes, and supplies. "
                "Select 'Barter' to browse my wares.",
        "speaker_id": "hw_vendor",
    }],
)

# Regular topics
addon.add_dialogue_topic(
    name="hub world",
    topic_type=0,
    responses=[{
        "id": "hw_info_hub_001",
        "prev_id": "",
        "next_id": "",
        "text": "The Hub connects the Garden, Forest, and Mine zones. "
                "Gather resources in each area: herbs, logs, ore. "
                "Use the Anvil and Forge to craft better gear. "
                "Zone passes are available from me.",
        "speaker_id": "hw_vendor",
    }],
)

addon.add_dialogue_topic(
    name="my trade",
    topic_type=0,
    responses=[{
        "id": "hw_info_trade_001",
        "prev_id": "",
        "next_id": "",
        "text": "I carry weapons, picks, alchemy apparatus, zone passes, "
                "and miscellaneous goods. My gold reserves are generous. "
                "I will buy whatever you harvest or craft.",
        "speaker_id": "hw_vendor",
    }],
)

addon.add_dialogue_topic(
    name="zone passes",
    topic_type=0,
    responses=[{
        "id": "hw_info_pass_001",
        "prev_id": "",
        "next_id": "",
        "text": "The Garden is open to all. The Forest and Mine require a "
                "pass - buy one from me. A Mine Refresh Token resets the "
                "ore deposits if they run dry.",
        "speaker_id": "hw_vendor",
    }],
)

# ===========================================================================
# MWSCRIPT — override EnableMenus to spawn the player in IdleMW
# ===========================================================================
# The game template's EnableMenus script calls
#   Player->PositionCell ... "Chamber of Initiation"
# Since hub_world.omwaddon loads last, our SCPT record with the same name
# replaces it entirely.  OpenMW compiles SCTX on load; no SCDT needed.
addon.add_script(
    id="EnableMenus",
    source=(
        "Begin EnableMenus\n"
        "\n"
        ";Enables all menus visible during normal gameplay\n"
        "\n"
        "EnableMagicMenu\n"
        "EnableInventoryMenu\n"
        "EnableMapMenu\n"
        "EnableStatsMenu\n"
        "EnableRest\n"
        "set CharGenState to -1\n"
        "\n"
        "Player->PositionCell 0, -300, 0, 0, \"IdleMW\"\n"
        "\n"
        "stopscript EnableMenus\n"
        "\n"
        "End EnableMenus\n"
    ),
)

# ===========================================================================
# CELLS
# ===========================================================================

# ---------------------------------------------------------------------------
# HUB WORLD — main lobby  (all positions scaled to 60 % of original design)
# ---------------------------------------------------------------------------
# Room walls at ±1320, floor 2880×2880.
# Door activators placed at ±1290 (10 GU inside each wall).
# ---------------------------------------------------------------------------
hub = addon.add_interior_cell(
    "IdleMW",
    flags=["illegal_to_sleep"],
    ambient=0x888888FF,   # neutral mid-gray ambient so material colours show
    fog_color=0x222222FF,
    fog_density=0.1,
)

# Floor, ceiling, and walls — mesh files generated by generate_meshes.py
hub.place_static("hw_floor_hub",    x=0,     y=0,    z=-10)       # floor
hub.place_static("hw_floor_hub",    x=0,     y=0,    z=490)       # ceiling
# N/S walls: wall_hub.dae is long in X — place with no rotation
hub.place_static("hw_wall_hub",     x=0,     y=1320, z=0)         # north
hub.place_static("hw_wall_hub",     x=0,     y=-1320, z=0)        # south
# E/W walls: wall_hub_ew.dae is long in Y — place with no rotation
hub.place_static("hw_wall_hub_ew",  x=1320,  y=0,    z=0)         # east
hub.place_static("hw_wall_hub_ew",  x=-1320, y=0,    z=0)         # west

# Ceiling light — central
hub.place_light("hw_light_ceiling", x=0, y=0, z=500)

# Decorative pillars at quadrant corners
for px, py in [(-900, 900), (900, 900), (900, -900), (-900, -900)]:
    hub.place_static("hw_pillar", x=px, y=py, z=0)

# Fill lights near pillars — neutral white
for lx, ly in [(-780, 780), (780, 780), (780, -780), (-780, -780)]:
    hub.place_light("hw_light_fill", x=lx, y=ly, z=200)

# Vending machine: STAT provides the visual, NPC sits just in front so it is
# clickable.  NPCs in the game template require basicplayer.dae for the
# skeleton — custom meshes without skeleton bindings render as collapsed blobs.
hub.place_static("hw_vending_machine", x=0, y=80, z=0)
hub.place_npc("hw_vendor", x=0, y=30, z=0, rotation=3.14159)  # face south, toward player spawn

# Bed — SE alcove
hub.place_activator("hw_bed", x=420, y=-360, z=0)

# Crafting stations — NW area
hub.place_activator("hw_anvil", x=-420, y=360, z=0)
hub.place_activator("hw_forge", x=-570, y=360, z=0)
hub.place_light("hw_light_forge_glow", x=-510, y=420, z=350)   # forge glow

# Mine Management Board — near south (mine) door
hub.place_activator("hw_mine_refresh_station", x=0, y=-1020, z=0)

# --- Doors (at walls ±1320; placed 30 GU inside so they sit flush) ---
# Garden door — north wall (real DOOR: engine handles teleport natively)
hub.place_door("hw_door_garden",  x=0, y=1290, z=0,
               destination_cell="Hub Garden", destination_pos=(0, -450, 0))

# Forest door — east wall
hub.place_activator("hw_door_forest",  x=1290,  y=0,     z=0, rot_z=1.5708)

# Mine door — south wall
hub.place_activator("hw_door_mine",    x=0,     y=-1290, z=0)

# ---------------------------------------------------------------------------
# HUB GARDEN  (60 % scale — floor 1320×1320)
# ---------------------------------------------------------------------------
garden = addon.add_interior_cell(
    "Hub Garden",
    flags=["illegal_to_sleep"],
    ambient=0x88AA66FF,
    fog_color=0x3A5F2AFF,
    fog_density=0.05,
)

garden.place_static("hw_floor_garden", x=0, y=0, z=-10)
garden.place_light("hw_light_garden",  x=0,    y=0,    z=400)
garden.place_light("hw_light_garden",  x=-360, y=-240, z=300)
garden.place_light("hw_light_garden",  x=300,  y=240,  z=300)

# Return door (south, leads back to Hub World — real DOOR record)
garden.place_door("hw_door_return_garden", x=0, y=-540, z=0,
                  destination_cell="IdleMW", destination_pos=(0, 1020, 0))

# Basil plants (5)
BASIL_POS = [(-300, 180), (-60, 360), (150, 240), (270, -60), (-210, -180)]
for i, (bx, by) in enumerate(BASIL_POS, 1):
    garden.place_activator(f"hw_plant_basil_{i:02d}", x=bx, y=by, z=0)

# Mint plants (5)
MINT_POS = [(300, 300), (-120, -300), (210, -240), (-330, -90), (90, -120)]
for i, (mx, my) in enumerate(MINT_POS, 1):
    garden.place_activator(f"hw_plant_mint_{i:02d}", x=mx, y=my, z=0)

# ---------------------------------------------------------------------------
# HUB FOREST  (60 % scale — floor 1800×1800)
# ---------------------------------------------------------------------------
forest = addon.add_interior_cell(
    "Hub Forest",
    flags=["illegal_to_sleep"],
    ambient=0x3A5F2AFF,
    fog_color=0x1A2F0AFF,
    fog_density=0.08,
)

forest.place_static("hw_floor_forest", x=0, y=0, z=-10)
forest.place_light("hw_light_forest",  x=0,    y=0,    z=500)
forest.place_light("hw_light_forest",  x=-480, y=-360, z=400)
forest.place_light("hw_light_forest",  x=420,  y=420,  z=400)
forest.place_light("hw_light_fill",    x=0,    y=-660, z=200)   # near entrance

# Return door (south/entrance)
forest.place_activator("hw_door_return_forest", x=0, y=-720, z=0)

# Trees (6)
TREE_POS = [(-480, -480), (-120, -360), (300, -420),
             (-540, 120),  (180, 180),  (420, 480)]
for i, (tx, ty) in enumerate(TREE_POS, 1):
    forest.place_activator(f"hw_tree_{i:02d}", x=tx, y=ty, z=0)

# Healing mushrooms (4)
MUSH_HEAL_POS = [(-360, -120), (120, -240), (360, 60), (-180, 360)]
for i, (hx, hy) in enumerate(MUSH_HEAL_POS, 1):
    forest.place_activator(f"hw_mushroom_heal_{i:02d}", x=hx, y=hy, z=0)

# Vigor mushrooms (4)
MUSH_VIG_POS = [(-420, 240), (60, -480), (420, 300), (-60, 120)]
for i, (vx, vy) in enumerate(MUSH_VIG_POS, 1):
    forest.place_activator(f"hw_mushroom_vigor_{i:02d}", x=vx, y=vy, z=0)

# ---------------------------------------------------------------------------
# HUB MINE  (60 % scale — floor 1320×1080)
# ---------------------------------------------------------------------------
mine = addon.add_interior_cell(
    "Hub Mine",
    flags=["illegal_to_sleep"],
    ambient=0x222222FF,
    fog_color=0x111111FF,
    fog_density=0.15,
)

mine.place_static("hw_floor_mine", x=0, y=0, z=-10)

# Torch lights
for lx, ly in [(-360, 240), (360, 240), (-360, -120), (360, -120), (0, 420)]:
    mine.place_light("hw_light_mine", x=lx, y=ly, z=220)

# Return door
mine.place_activator("hw_door_return_mine", x=0, y=510, z=0)

# Iron ore deposits (8)
IRON_POS = [(-300, 240), (-120, 120), (60, 240), (240, 120),
             (-360, -60), (-180, -180), (120, -240), (300, -120)]
for i, (ix, iy) in enumerate(IRON_POS, 1):
    mine.place_activator(f"hw_mineral_iron_{i:02d}", x=ix, y=iy, z=0)

# Stone deposits (4)
STONE_POS = [(-420, 60), (180, -300), (360, 210), (-240, 300)]
for i, (sx, sy) in enumerate(STONE_POS, 1):
    mine.place_activator(f"hw_mineral_stone_{i:02d}", x=sx, y=sy, z=0)

# ===========================================================================
# SAVE
# ===========================================================================

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub_world.omwaddon")
addon.save(out)
print(f"Saved: {out}")

# Quick validation
from tes3.reader import read_file
from tools.validate import validate
records = read_file(out)
result = validate(records)
if result.ok:
    print("Validation OK")
else:
    for e in result.errors:
        print(f"  ERROR: {e}")
    for w in result.warnings:
        print(f"  WARN:  {w}")
