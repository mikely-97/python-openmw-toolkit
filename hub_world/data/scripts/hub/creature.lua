--[[
hub_world/data/scripts/hub/creature.lua
LOCAL script — runs on every CREATURE in the loaded game world.

DEBUG BUILD: set DEBUG = false to silence HUD messages after testing.

Weapon-type immunity logic:
  idlemw_tree            → only axes (types 7, 8) deal damage
  idlemw_iron_deposit    → only blunt/pickaxe (types 3-5) deal damage
  idlemw_stone_deposit   → same as iron

Uses onUpdate + health-delta detection because onHit is not in the
documented 0.50 engine handler list.
]]

local self_m = require('openmw.self')
local types  = require('openmw.types')
local nearby = require('openmw.nearby')

local DEBUG = true   -- set false to stop showing HUD messages

-- ---------------------------------------------------------------------------
-- Config
-- ---------------------------------------------------------------------------

local CREATURE_CFG = {
    idlemw_tree          = { [7] = true, [8] = true },
    idlemw_iron_deposit  = { [3] = true, [4] = true, [5] = true },
    idlemw_stone_deposit = { [3] = true, [4] = true, [5] = true },
}

local prevHealth  = nil
local initialized = false   -- one-time init log guard

-- ---------------------------------------------------------------------------
-- Debug helpers
-- ---------------------------------------------------------------------------

-- Writes to the OpenMW log file (always) and to the player's HUD (if DEBUG).
local function dbg(text)
    local msg = "[HW CREA] " .. text
    print(msg)
    if not DEBUG then return end
    pcall(function()
        for _, actor in ipairs(nearby.actors) do
            local ok, isP = pcall(function() return types.Actor.isPlayer(actor) end)
            if ok and isP then
                actor:sendEvent("HW_ShowMsg", { text = msg })
                return
            end
        end
    end)
end

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local function findPlayer()
    for _, actor in ipairs(nearby.actors) do
        local ok, isP = pcall(function() return types.Actor.isPlayer(actor) end)
        if ok and isP then return actor end
    end
    return nil
end

local function getEquippedWeaponType(actor)
    local equip
    pcall(function() equip = types.Actor.getEquipment(actor) end)
    if not equip then return nil end
    for _, item in pairs(equip) do
        if item then
            local ok, wtype = pcall(function()
                return types.Weapon.record(item.recordId).type
            end)
            if ok and type(wtype) == "number" then return wtype end
        end
    end
    return nil
end

-- ---------------------------------------------------------------------------
-- Main update loop
-- ---------------------------------------------------------------------------

local function onUpdate(dt)
    local rid = self_m.object.recordId
    local cfg = CREATURE_CFG[rid]
    if not cfg then return end

    -- One-time init message so we can confirm the script is running on this CREA.
    if not initialized then
        initialized = true
        dbg("active on " .. rid)
    end

    local currHealth
    local hok, herr = pcall(function()
        currHealth = types.Actor.stats.dynamic.health(self_m.object).current
    end)
    if not hok then
        dbg("health read error: " .. tostring(herr))
        return
    end
    if not currHealth then
        dbg("WARNING: health is nil on " .. rid)
        return
    end

    if prevHealth and currHealth < prevHealth then
        -- Health dropped — log and check weapon type.
        dbg(rid .. " HP drop: " .. prevHealth .. " -> " .. currHealth)

        local player = findPlayer()
        if not player then
            dbg("WARNING: could not find player")
            prevHealth = currHealth
            return
        end

        local wtype = getEquippedWeaponType(player)
        dbg("player weapon type: " .. tostring(wtype))

        local isVulnerable = (wtype ~= nil) and (cfg[wtype] == true)
        dbg("vulnerable: " .. tostring(isVulnerable))

        if not isVulnerable then
            local ok, err = pcall(function()
                types.Actor.stats.dynamic.health(self_m.object).current = prevHealth
            end)
            if ok then
                dbg("HP restored to " .. prevHealth)
                currHealth = prevHealth  -- keep baseline correct for next frame
            else
                dbg("restore FAILED: " .. tostring(err))
            end
        end
    end

    if currHealth > 0 then
        prevHealth = currHealth
    end
end

-- ---------------------------------------------------------------------------
-- Export
-- ---------------------------------------------------------------------------

return {
    engineHandlers = {
        onUpdate = onUpdate,
    },
}
