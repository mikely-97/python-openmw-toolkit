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

    -- Diagnostic: confirm activation fires and LOCAL→PLAYER event routing works.
    -- Remove this block once plants are confirmed interactable.
    pcall(function()
        actor:sendEvent("HW_ShowMsg", { text = "[HW] activated: " .. rid })
    end)

    core.sendGlobalEvent("HW_Activate", {
        recordId = rid,
        objectId = rid,            -- unique per template; .id is nil in OpenMW 0.50
        object   = self_m.object,  -- world-object ref so GLOBAL can hide/show
        actor    = actor,
    })
end

-- GLOBAL sends these when a plant is harvested / respawns.
-- Fallback path: if world.setObjectEnabled is unavailable in GLOBAL,
-- it forwards to here and we try setting our own scale.
local function onHW_Hide()
    pcall(function() self_m.object.scale = 0.001 end)
end

local function onHW_Show()
    pcall(function() self_m.object.scale = 1.0 end)
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
