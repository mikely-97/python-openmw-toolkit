--[[
hub_world/data/scripts/hub/activator.lua
LOCAL script — runs on every ACTIVATOR in the game world.

It filters for Hub World activator IDs and forwards to the GLOBAL script
via sendGlobalEvent.  All world-mutation happens there.

The script also handles the mine_generation counter (allows mine refresh
to clear depletion state using only per-object storage keys).
]]

local self_m = require('openmw.self')
local core   = require('openmw.core')
local types  = require('openmw.types')
local storage= require('openmw.storage')

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
        objectId = tostring(self_m.object.id),  -- unique instance identifier
        actor    = actor,
    })
end

return {
    engineHandlers = {
        onActivated = onActivate,   -- LOCAL handler is onActivated(actor)
    },
}
