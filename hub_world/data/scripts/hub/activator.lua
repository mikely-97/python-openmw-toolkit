--[[
hub_world/data/scripts/hub/activator.lua
LOCAL script — runs on every ACTIVATOR in the game world.

It filters for Hub World activator IDs and forwards to the GLOBAL script
via sendGlobalEvent.  All world-mutation happens there.

HW_Hide / HW_Show events: GLOBAL cannot write object scale/position (read-only
from GLOBAL context).  These events delegate scale changes to the LOCAL script,
which CAN write self_m.object.scale on its own object.
]]

local self_m = require('openmw.self')
local core   = require('openmw.core')
local types  = require('openmw.types')

-- Set of Hub World ACTI recordIds that are actually placed in cells.
-- Trees and mineral deposits are now NPC_/CREA — combat-based, not listed here.
-- Doors are now native DOOR records — engine handles teleportation directly.
local HW_IDS = {
    -- Garden plants (single record, 5 instances each)
    hw_plant_basil_01 = true,
    hw_plant_mint_01  = true,
    -- Forest mushrooms (single record, 4 instances each)
    hw_mushroom_heal_01  = true,
    hw_mushroom_vigor_01 = true,
    -- Hub stations
    hw_bed                    = true,
    hw_mine_refresh_station   = true,
    hw_vending_machine_garden = true,
}

local function onActivate(actor)
    local rid = self_m.object.recordId
    if not HW_IDS[rid] then return end

    -- Only handle player activations; other actors are ignored
    local ok, isPlayer = pcall(function()
        return types.Actor.isPlayer and types.Actor.isPlayer(actor)
    end)
    if ok and isPlayer == false then return end

    core.sendGlobalEvent("HW_Activate", {
        recordId = rid,
        objectId = rid,            -- unique per template; .id is nil in OpenMW 0.50
        object   = self_m.object,  -- world-object ref so GLOBAL can reference it
        actor    = actor,
    })
end

-- GLOBAL sends HW_Hide when a plant is harvested.
-- data.actor: the harvesting player (for error reporting).
-- LOCAL scripts can write self_m.object.scale on their own object;
-- GLOBAL script writes to object.scale/position are rejected as read-only.
local function onHW_Hide(data)
    local actor = data and data.actor
    local ok, err = pcall(function()
        self_m.object.scale = 0.001
    end)
    if not ok and actor then
        pcall(function()
            actor:sendEvent("HW_ShowMsg", { text = "[HW LOC HIDE ERR] " .. tostring(err) })
        end)
    end
end

local function onHW_Show(data)
    local actor = data and data.actor
    local ok, err = pcall(function()
        self_m.object.scale = 1.0
    end)
    if not ok and actor then
        pcall(function()
            actor:sendEvent("HW_ShowMsg", { text = "[HW LOC SHOW ERR] " .. tostring(err) })
        end)
    end
end

return {
    engineHandlers = {
        onActivated = onActivate,   -- LOCAL handler is onActivated(actor)
    },
    eventHandlers = {
        HW_Hide = onHW_Hide,
        HW_Show = onHW_Show,
    },
}
