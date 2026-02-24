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

-- Set of all Hub World activator recordIds this script cares about
local HW_IDS = {
    -- Garden plants
    hw_plant_basil_01=true, hw_plant_basil_02=true, hw_plant_basil_03=true,
    hw_plant_basil_04=true, hw_plant_basil_05=true,
    hw_plant_mint_01=true,  hw_plant_mint_02=true,  hw_plant_mint_03=true,
    hw_plant_mint_04=true,  hw_plant_mint_05=true,
    -- Forest mushrooms
    hw_mushroom_heal_01=true, hw_mushroom_heal_02=true,
    hw_mushroom_heal_03=true, hw_mushroom_heal_04=true,
    hw_mushroom_vigor_01=true,hw_mushroom_vigor_02=true,
    hw_mushroom_vigor_03=true,hw_mushroom_vigor_04=true,
    -- Forest trees
    hw_tree_01=true, hw_tree_02=true, hw_tree_03=true,
    hw_tree_04=true, hw_tree_05=true, hw_tree_06=true,
    -- Mine minerals
    hw_mineral_iron_01=true, hw_mineral_iron_02=true,
    hw_mineral_iron_03=true, hw_mineral_iron_04=true,
    hw_mineral_iron_05=true, hw_mineral_iron_06=true,
    hw_mineral_iron_07=true, hw_mineral_iron_08=true,
    hw_mineral_stone_01=true,hw_mineral_stone_02=true,
    hw_mineral_stone_03=true,hw_mineral_stone_04=true,
    -- Stations
    hw_bed=true, hw_anvil=true, hw_forge=true,
    hw_mine_refresh_station=true,
    -- Garden herb collector (mini vending machine)
    hw_vending_machine_garden=true,
    -- Doors (only ACTI doors — garden uses real DOOR records handled by engine)
    hw_door_forest=true,
    hw_door_mine=true,
    hw_door_return_forest=true,
    hw_door_return_mine=true,
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
