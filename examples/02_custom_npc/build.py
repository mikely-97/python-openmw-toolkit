"""Example 02 — Custom NPC placed in an interior cell.

Creates a vendor NPC and places them in an interior shop cell.

Usage:
    poetry run python examples/02_custom_npc/build.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from addon import AddonBuilder

addon = AddonBuilder(
    description="Custom NPC example",
    masters=["template.omwgame"],
)

# Add the NPC
addon.add_npc(
    id="example_merchant_01",
    name="Grulnax the Vendor",
    race="Orc",
    npc_class="Merchant",
    faction="",
    disposition=60,
    level=5,
    gold=500,
    flags=["autocalc"],
    services=0x0004,  # barter
    inventory=[
        ("iron longsword", 2),
        ("bread", 10),
        ("ale", 5),
    ],
)

# Add a light source for the shop
addon.add_light(
    id="example_shop_lamp",
    name="Shop Lamp",
    radius=200,
    color=(255, 220, 140),
    flags=["can_carry", "dynamic"],
    duration=-1,
)

# Create the interior cell and furnish it
cell = addon.add_interior_cell(
    "Grulnax's Shop",
    flags=["illegal_to_sleep"],
    ambient=0x404040FF,
)

cell.place_npc("example_merchant_01", x=0.0, y=128.0, z=0.0, rotation=0.0)
cell.place_light("example_shop_lamp", x=0.0, y=0.0, z=180.0)

out = Path(__file__).parent / "custom_npc.omwaddon"
addon.save(out)
print(f"Written: {out}")
