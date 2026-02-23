"""Example 01 — Hello World: minimal addon with a single GLOB record.

This is the simplest possible addon: one global variable.
Load it in OpenMW and run `ShowGlobals` in the console to see MyAddon_Loaded = 1.

Usage:
    poetry run python examples/01_hello_world/build.py
    # → output: examples/01_hello_world/hello_world.omwaddon
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from addon import AddonBuilder

addon = AddonBuilder(
    description="Hello World - minimal example addon",
    company="Example",
    masters=["template.omwgame"],
)

addon.add_global("MyAddon_Loaded", type="short", value=1)

out = Path(__file__).parent / "hello_world.omwaddon"
addon.save(out)
print(f"Written: {out}")
