"""Example 03 — Scripted Item: a misc item with attached MWScript.

The script prints a message when the item is equipped.
OpenMW compiles SCTX source on load (no bytecode required).

Usage:
    poetry run python examples/03_scripted_item/build.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from addon import AddonBuilder

SCRIPT_SOURCE = """\
Begin example_orb_script

short equipped

if ( MenuMode == 0 )
    if ( GetItemCount "example_orb_01" > 0 )
        if ( equipped == 0 )
            set equipped to 1
            MessageBox "The orb pulses with energy."
        endif
    else
        set equipped to 0
    endif
endif

End
"""

addon = AddonBuilder(
    description="Scripted item example",
    masters=["template.omwgame"],
)

# Attach a MWScript
addon.add_script(
    id="example_orb_script",
    source=SCRIPT_SOURCE,
    num_shorts=1,
    variables=["equipped"],
)

# The misc item that uses the script
addon.add_misc_item(
    id="example_orb_01",
    name="Pulsing Orb",
    weight=0.5,
    value=50,
    script="example_orb_script",
)

out = Path(__file__).parent / "scripted_item.omwaddon"
addon.save(out)
print(f"Written: {out}")
