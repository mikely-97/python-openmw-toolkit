"""Example 04 — Lua Global Script.

A GLOBAL Lua script that runs a timer and logs a message every 5 seconds.
The addon binary is minimal (just a GLOB for version tracking).
The actual Lua file lives at data/scripts/example/global.lua and is
registered via an .omwscripts file.

Usage:
    poetry run python examples/04_lua_global/build.py
    # Then add to openmw.cfg:
    #   data="path/to/examples/04_lua_global"
    #   content=lua_global_example.omwaddon
    #   content=lua_global_example.omwscripts
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from addon import AddonBuilder

addon = AddonBuilder(
    description="Lua global script example",
    masters=["template.omwgame"],
)

addon.add_global("LuaExample_Version", type="short", value=1)

out_dir = Path(__file__).parent
out_addon = out_dir / "lua_global_example.omwaddon"
addon.save(out_addon)
print(f"Written: {out_addon}")

# Write the .omwscripts manifest (plain text, not binary)
omwscripts = out_dir / "lua_global_example.omwscripts"
omwscripts.write_text("GLOBAL: scripts/example/global.lua\n")
print(f"Written: {omwscripts}")

# Write the Lua script
scripts_dir = out_dir / "data" / "scripts" / "example"
scripts_dir.mkdir(parents=True, exist_ok=True)
lua_path = scripts_dir / "global.lua"
lua_path.write_text("""\
-- Example GLOBAL script: logs a message every 5 seconds.
local core = require('openmw.core')
local async = require('openmw.async')

local interval = 5.0
local elapsed = 0.0

local function onUpdate(dt)
    elapsed = elapsed + dt
    if elapsed >= interval then
        elapsed = 0.0
        print("[LuaExample] Heartbeat: " .. tostring(core.getGameTime()))
    end
end

return {
    engineHandlers = {
        onUpdate = onUpdate,
    }
}
""")
print(f"Written: {lua_path}")
