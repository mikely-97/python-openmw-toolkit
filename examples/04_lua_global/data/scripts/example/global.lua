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
