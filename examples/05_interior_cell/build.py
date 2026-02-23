"""Example 05 — Interior Cell with placed objects and a connecting door.

Demonstrates:
- Interior cell with ambient lighting
- Placed static objects, a container, and a door
- Door teleport destination wired to another cell

Usage:
    poetry run python examples/05_interior_cell/build.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from addon import AddonBuilder

addon = AddonBuilder(
    description="Interior cell example",
    masters=["template.omwgame"],
)

# A chest with some loot
addon.add_container(
    id="example_chest_01",
    name="Old Chest",
    capacity=200.0,
    inventory=[
        ("Gold_001", 25),
    ],
)

# A torch
addon.add_light(
    id="example_torch_wall",
    radius=150,
    color=(255, 180, 80),
    flags=["dynamic", "fire"],
    duration=-1,
)

# A book on a shelf
addon.add_book(
    id="example_journal_01",
    name="Traveller's Journal",
    weight=0.5,
    value=15,
    text=(
        "<DIV ALIGN=CENTER><FONT SIZE=4><BR>Traveller's Journal</FONT></DIV>"
        "<BR>Day 1: Arrived in the Hub. The locals seem friendly enough."
        "<BR>Day 2: Found a peculiar chest. Contents: 25 gold coins."
    ),
)

# Levelled list for randomized loot
addon.add_levelled_list(
    id="example_random_loot",
    items=[
        ("iron longsword", 1),
        ("leather cuirass", 1),
        ("example_journal_01", 3),
    ],
    chance_none=20,
)

# Build the interior cell
cell = addon.add_interior_cell(
    "The Old Storeroom",
    flags=["illegal_to_sleep"],
    ambient=0x303030FF,
    fog_color=0x101010FF,
    fog_density=0.3,
)

# Place objects
cell.place_container("example_chest_01", x=200.0, y=0.0, z=0.0)
cell.place_light("example_torch_wall", x=-200.0, y=0.0, z=180.0)
cell.place_item("example_journal_01", x=100.0, y=50.0, z=0.0)

# Wire a door leading back to The Hub
cell.place_door(
    door_id="example_door_01",
    x=0.0,
    y=-300.0,
    z=0.0,
    destination_cell="The Hub",
    destination_pos=(0.0, 0.0, 0.0),
)

out = Path(__file__).parent / "interior_cell.omwaddon"
addon.save(out)
print(f"Written: {out}")
