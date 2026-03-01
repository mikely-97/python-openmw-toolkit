--[[
hub_world/data/scripts/hub/global.lua
GLOBAL script — owns all game-state mutations for the Hub World addon.

Architecture
------------
* LOCAL activator script sends core.sendGlobalEvent("HW_Activate", data)
* This script handles it: checks cooldowns, modifies inventory, sends
  HW_ShowMsg event back to the player's LOCAL/PLAYER script.
* All persistent state lives in openmw.storage.globalSection("HubWorld").

OpenMW Lua API notes used here
-------------------------------
  core.getGameTimeInSeconds()     – game time in seconds since dawn-of-days
  types.Actor.inventory(actor)    – returns InventoryStore
    :add(id, count)               – add items  (allowed from GLOBAL scripts)
    :countOf(id)                  – count stacked items
    :remove(id, count)            – remove items
  types.Actor.getEquipment(actor) – returns table[slot] → item stack
  types.Actor.EQUIPMENT_SLOT      – enum of equipment slot constants
  types.NPC.stats.skills          – skill accessor (NPC + player)
    .<skillName>(actor).base      – base skill value (read/write)
  world.teleportActor(actor, cell, pos, rot) – move actor to cell
  world.getCellByName(name)       – find interior cell
  world.getPlayer()               – player world object
  world.setObjectEnabled(obj, bool) – show/hide world object (0.50+)
  openmw.util.vector3(x,y,z)     – 3-component vector

Plant respawn system
--------------------
  Plants use two parallel timers:
    1. Storage key "harvest_<rid>": game-time readyAt (persists across saves).
       ~9000 game-seconds ≈ 5 real minutes at the default timescale of 30.
    2. plant_objects[rid]: real-time readyAt using accumulated dt.
       Visual hide/show is session-only; storage check is the authority.
]]

local storage = require('openmw.storage')
local core    = require('openmw.core')
local world   = require('openmw.world')
local types   = require('openmw.types')
local util    = require('openmw.util')

local G = storage.globalSection("HubWorld")

-- ---------------------------------------------------------------------------
-- Session-only state (not persisted)
-- ---------------------------------------------------------------------------

local realTimeAccum   = 0.0   -- accumulated real seconds since game load
local plant_objects   = {}    -- rid → {recordId, cellName, position, readyAt, shown}
local countdown_timer = 0.0   -- time since last countdown update to player

-- Safe wrapper: core.getGameTimeInSeconds() is not available in all OpenMW
-- 0.50 builds.  Falls back to real-time × default timescale (30) so that
-- tree/mineral cooldowns are approximate but never crash.
local function getGameTime()
    local ok, t = pcall(function() return core.getGameTimeInSeconds() end)
    return (ok and type(t) == "number") and t or (realTimeAccum * 30)
end

-- ---------------------------------------------------------------------------
-- Configuration tables
-- ---------------------------------------------------------------------------

local SECS_PER_HOUR      = 3600
local PLANT_RESPAWN_REAL = 5     -- seconds until a harvested garden plant reappears
local PLANT_RESPAWN_GAME = 9000  -- ≈5 min at timescale 30 (storage cooldown)

local PLANT_DISPLAY_NAMES = {
    hw_plant_basil    = "Garden Basil",
    hw_plant_mint     = "Garden Mint",
    hw_mushroom_heal  = "Heal Mushroom",
    hw_mushroom_vigor = "Vigor Mushroom",
}

-- Items granted by each harvestable activator recordId.
-- Trees and mineral deposits are now CREA/NPC_ objects — combat-based, no entry here.
local HARVEST_CFG = {
    -- Garden plants (single record, multiple instances placed in cell)
    hw_plant_basil_01 = { item="hw_herb_basil" },
    hw_plant_mint_01  = { item="hw_herb_mint"  },
    -- Forest mushrooms
    hw_mushroom_heal_01  = { item="hw_mushroom_heal",  respawn=24*SECS_PER_HOUR },
    hw_mushroom_vigor_01 = { item="hw_mushroom_vigor", respawn=24*SECS_PER_HOUR },
}



-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local function sendMsg(actor, text)
    actor:sendEvent("HW_ShowMsg", { text = text })
end

-- Correct OpenMW 0.50 API for inventory mutation (GLOBAL scripts only):
--   world.createObject(id, count):moveInto(types.Actor.inventory(actor))  – add
--   types.Actor.inventory(actor):find(id):remove(count)                   – remove
-- world.createObject(id, N) with N > 1 triggers Morrowind's gold denomination
-- lookup: N=5 → "gold_005", N=10 → "gold_010", etc.  Only non-gold MISC items
-- accept N > 1 safely.  Work around by looping with count=1 for all items.
local function giveItem(actor, id, count)
    local n = math.max(1, math.floor(count or 1))
    for i = 1, n do
        local ok, err = pcall(function()
            world.createObject(id, 1):moveInto(types.Actor.inventory(actor))
        end)
        if not ok then
            sendMsg(actor, "[HW GIVE ERR] " .. tostring(id) .. ": " .. tostring(err))
            return
        end
    end
end

local function takeItem(actor, id, count)
    pcall(function()
        local stack = types.Actor.inventory(actor):find(id)
        if stack then stack:remove(count or 1) end
    end)
end

local function getSkill(actor, skillName)
    local ok, val = pcall(function()
        return types.NPC.stats.skills[skillName](actor).base
    end)
    if ok then return val end
    return 10
end

local function trainSkill(actor, skillName, amount)
    pcall(function()
        local stat = types.NPC.stats.skills[skillName](actor)
        stat.base = stat.base + amount
    end)
end

-- Hide a harvested plant by removing it from the world.
-- Object properties (scale, position) are read-only from all Lua script types
-- in OpenMW 0.50; removal + recreation is the only reliable hide/show path.
local function hideObject(obj, actor)
    if not obj then return end
    local ok, err = pcall(function() obj:remove() end)
    if not ok and actor then
        sendMsg(actor, "[HW HIDE ERR] " .. tostring(err))
    end
end

-- Recreate a plant at the position/cell stored in its plant_objects entry.
-- world.createObject() starts disabled; :teleport() places + enables in one step.
local function recreatePlant(info)
    local pok, player = pcall(function() return world.getPlayer() end)
    local function gp(text)
        if pok and player then pcall(function() sendMsg(player, text) end) end
    end

    if not info.cellName or not info.position then
        gp("[HW RESPAWN] missing data for " .. tostring(info.recordId))
        return
    end

    local ok, err = pcall(function()
        local obj = world.createObject(info.recordId, 1)
        obj:teleport(info.cellName, info.position)
    end)

    if ok then
        gp("[HW RESPAWN] " .. info.recordId .. " placed in '" .. info.cellName .. "'")
    else
        gp("[HW RESPAWN ERR] " .. tostring(err))
    end
end

-- Friendly display name for a harvestable activator recordId.
-- Strips trailing _01/_02 instance suffix, looks up in display names table.
local function getPlantDisplayName(rid)
    local base = rid:match("^(hw_%a+_%a+)_%d+$") or rid:match("^(hw_%a+)_%d+$")
    return PLANT_DISPLAY_NAMES[base] or rid:gsub("_", " ")
end

-- Seconds until the last-harvested garden plant respawns (real time).
-- Returns 0 when all plants have respawned (or none were harvested this session).
local function getGardenCountdownSecs()
    local maxLeft = 0
    for _, info in pairs(plant_objects) do
        if not info.shown then
            local left = info.readyAt - realTimeAccum
            if left > maxLeft then maxLeft = left end
        end
    end
    return math.max(0, math.floor(maxLeft))
end

-- ---------------------------------------------------------------------------
-- Plant / mushroom pickup (garden plants + forest mushrooms)
-- ---------------------------------------------------------------------------

local function handlePlant(recordId, actor, worldObject)
    local cfg = HARVEST_CFG[recordId]
    if not cfg then return end

    -- All harvestable activators use position-keyed instance tracking (many-1
    -- pattern: multiple cell instances share one recordId).
    local pos, cell_name, posKey
    if worldObject then
        pcall(function()
            pos       = worldObject.position
            cell_name = worldObject.cell and worldObject.cell.name or ""
        end)
        if pos then
            posKey = string.format("%.0f_%.0f_%.0f", pos.x, pos.y, pos.z)
            local existing = plant_objects[posKey]
            if existing and not existing.shown then
                sendMsg(actor, "This plant has not grown back yet.")
                return
            end
        end
    end

    -- Grant ingredient
    giveItem(actor, cfg.item, 1)

    -- Remove from world and start real-time respawn timer.
    if worldObject and posKey then
        plant_objects[posKey] = {
            recordId = recordId,
            position = pos,
            cellName = cell_name,
            readyAt  = realTimeAccum + PLANT_RESPAWN_REAL,
            shown    = false,
        }
        hideObject(worldObject, actor)
    end

    sendMsg(actor, "You have successfully harvested " .. getPlantDisplayName(recordId) .. ".")
end

-- ---------------------------------------------------------------------------
-- Mine refresh
-- ---------------------------------------------------------------------------

local function handleMineRefresh(actor)
    local inv = types.Actor.inventory(actor)
    if inv:countOf("hw_mine_refresh") == 0 then
        sendMsg(actor,
            "The Mine Management Board requires a Mine Refresh Token. "
            .. "Buy one from the vendor.")
        return
    end

    takeItem(actor, "hw_mine_refresh", 1)
    G:set("mine_refresh_pending", true)
    sendMsg(actor, "Mine refresh token used! The deposits will be available again.")
end

-- ---------------------------------------------------------------------------
-- Bed — rest / stat restore
-- ---------------------------------------------------------------------------

local function handleBed(actor)
    pcall(function()
        local h = types.Actor.stats.health(actor)
        h.current = h.base
        local m = types.Actor.stats.magicka(actor)
        m.current = m.base
        local f = types.Actor.stats.fatigue(actor)
        f.current = f.base
    end)
    sendMsg(actor, "You rest on the bed and recover fully.")
end

-- ---------------------------------------------------------------------------
-- Garden herb collector (mini vending machine)
-- Buys all herbs from the player at 5 gold each.
-- ---------------------------------------------------------------------------

local function handleGardenVendor(actor)
    local inv   = types.Actor.inventory(actor)
    local total = 0
    local parts = {}

    local herbs = { "hw_herb_basil", "hw_herb_mint" }
    for _, id in ipairs(herbs) do
        local n = inv:countOf(id)
        if n > 0 then
            takeItem(actor, id, n)
            total = total + n
            local label = id:match("hw_herb_(.+)$") or id
            label = label:sub(1,1):upper() .. label:sub(2)
            parts[#parts+1] = n .. "x " .. label
        end
    end

    if total > 0 then
        giveItem(actor, "Gold_001", total * 5)
        sendMsg(actor,
            "Herb Collector: sold " .. table.concat(parts, ", ")
            .. " for " .. (total * 5) .. " gold.")
    else
        sendMsg(actor, "Herb Collector: no herbs to sell.")
    end
end

-- ---------------------------------------------------------------------------
-- Main event dispatcher
-- ---------------------------------------------------------------------------

local function onHW_Activate(data)
    local rid   = data.recordId
    local actor = data.actor
    local obj   = data.object

    local ok, err = pcall(function()
        if HARVEST_CFG[rid] then
            handlePlant(rid, actor, obj)
        elseif rid == "hw_bed" then
            handleBed(actor)
        elseif rid == "hw_mine_refresh_station" then
            handleMineRefresh(actor)
        elseif rid == "hw_vending_machine_garden" then
            handleGardenVendor(actor)
        end
    end)

    if not ok then
        pcall(function()
            actor:sendEvent("HW_ShowMsg", { text = "[HW ERR] " .. tostring(err) })
        end)
    end
end

-- ---------------------------------------------------------------------------
-- Respawn checking + countdown broadcast
-- ---------------------------------------------------------------------------

local function checkPlantRespawns()
    for rid, info in pairs(plant_objects) do
        if not info.shown and realTimeAccum >= info.readyAt then
            info.shown = true
            local pok, player = pcall(function() return world.getPlayer() end)
            if pok and player then
                pcall(function()
                    sendMsg(player, "[HW] Respawn timer fired: " .. rid)
                end)
            end
            recreatePlant(info)
        end
    end
end

local function sendCountdownUpdate()
    local ok, player = pcall(function() return world.getPlayer() end)
    if not ok or not player then return end

    local cellName = ""
    pcall(function() cellName = player.cell.name end)

    local timeLeft
    if cellName == "Hub Garden" then
        timeLeft = getGardenCountdownSecs()
    else
        timeLeft = -1   -- tell player to hide widget
    end

    pcall(function()
        player:sendEvent("HW_Countdown", { timeLeft = timeLeft })
    end)
end

-- ---------------------------------------------------------------------------
-- Main update loop
-- ---------------------------------------------------------------------------

local function onUpdate(dt)
    realTimeAccum   = realTimeAccum   + dt
    countdown_timer = countdown_timer + dt

    checkPlantRespawns()

    if countdown_timer >= 1.0 then
        countdown_timer = 0
        sendCountdownUpdate()
    end

    if G:get("mine_refresh_pending") then
        G:set("mine_refresh_pending", false)
        G:set("mine_generation", (G:get("mine_generation") or 0) + 1)
    end
end

-- ---------------------------------------------------------------------------
-- Export
-- ---------------------------------------------------------------------------

return {
    engineHandlers = {
        onUpdate = onUpdate,
    },
    eventHandlers = {
        HW_Activate = onHW_Activate,
    },
}
