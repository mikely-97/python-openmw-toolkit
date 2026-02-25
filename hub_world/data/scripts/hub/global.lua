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
    hw_plant_basil = "Garden Basil",
    hw_plant_mint  = "Garden Mint",
}

-- Items granted by each harvestable activator recordId
local HARVEST_CFG = {
    -- plants (Garden)
    hw_plant_basil_01 = { item="hw_herb_basil" },
    hw_plant_basil_02 = { item="hw_herb_basil" },
    hw_plant_basil_03 = { item="hw_herb_basil" },
    hw_plant_basil_04 = { item="hw_herb_basil" },
    hw_plant_basil_05 = { item="hw_herb_basil" },
    hw_plant_mint_01  = { item="hw_herb_mint"  },
    hw_plant_mint_02  = { item="hw_herb_mint"  },
    hw_plant_mint_03  = { item="hw_herb_mint"  },
    hw_plant_mint_04  = { item="hw_herb_mint"  },
    hw_plant_mint_05  = { item="hw_herb_mint"  },
    -- mushrooms (Forest)
    hw_mushroom_heal_01 = { item="hw_mushroom_heal", respawn=24*SECS_PER_HOUR },
    hw_mushroom_heal_02 = { item="hw_mushroom_heal", respawn=24*SECS_PER_HOUR },
    hw_mushroom_heal_03 = { item="hw_mushroom_heal", respawn=24*SECS_PER_HOUR },
    hw_mushroom_heal_04 = { item="hw_mushroom_heal", respawn=24*SECS_PER_HOUR },
    hw_mushroom_vigor_01= { item="hw_mushroom_vigor",respawn=24*SECS_PER_HOUR },
    hw_mushroom_vigor_02= { item="hw_mushroom_vigor",respawn=24*SECS_PER_HOUR },
    hw_mushroom_vigor_03= { item="hw_mushroom_vigor",respawn=24*SECS_PER_HOUR },
    hw_mushroom_vigor_04= { item="hw_mushroom_vigor",respawn=24*SECS_PER_HOUR },
}

local TREE_CFG = {
    hw_tree_01 = { base_hp=5, respawn=7*24*SECS_PER_HOUR },
    hw_tree_02 = { base_hp=5, respawn=7*24*SECS_PER_HOUR },
    hw_tree_03 = { base_hp=6, respawn=7*24*SECS_PER_HOUR },
    hw_tree_04 = { base_hp=5, respawn=7*24*SECS_PER_HOUR },
    hw_tree_05 = { base_hp=7, respawn=7*24*SECS_PER_HOUR },
    hw_tree_06 = { base_hp=8, respawn=7*24*SECS_PER_HOUR },
}

local MINERAL_CFG = {
    hw_mineral_iron_01 = { item="hw_iron_ore" },
    hw_mineral_iron_02 = { item="hw_iron_ore" },
    hw_mineral_iron_03 = { item="hw_iron_ore" },
    hw_mineral_iron_04 = { item="hw_iron_ore" },
    hw_mineral_iron_05 = { item="hw_iron_ore" },
    hw_mineral_iron_06 = { item="hw_iron_ore" },
    hw_mineral_iron_07 = { item="hw_iron_ore" },
    hw_mineral_iron_08 = { item="hw_iron_ore" },
    hw_mineral_stone_01= { item="hw_stone"    },
    hw_mineral_stone_02= { item="hw_stone"    },
    hw_mineral_stone_03= { item="hw_stone"    },
    hw_mineral_stone_04= { item="hw_stone"    },
}

-- Weapons considered axes (Axe skill) for tree-chopping
local AXE_IDS = {
    hw_axe_wooden=true, hw_axe_iron=true, hw_axe_wooden_craft=true
}

-- Weapons considered pickaxes (Blunt skill) for mining
local PICKAXE_IDS = {
    hw_pickaxe_basic=true, hw_pickaxe_iron=true
}

-- Weapon quality multipliers for damage calculation
local WEAPON_POWER = {
    hw_axe_wooden       = 1.0,
    hw_axe_wooden_craft = 1.6,
    hw_axe_iron         = 2.5,
    hw_pickaxe_basic    = 1.0,
    hw_pickaxe_iron     = 2.0,
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

local function getEquippedWeaponId(actor)
    local equip = types.Actor.getEquipment(actor)
    local slot = types.Actor.EQUIPMENT_SLOT
        and (types.Actor.EQUIPMENT_SLOT.CarriedRight or 13)
        or 13
    local stack = equip[slot]
    if stack and stack.object then
        return stack.object.recordId
    end
    return nil
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

-- Friendly display name for a garden plant recordId.
local function getPlantDisplayName(rid)
    local base = rid:match("^(hw_plant_%a+)_%d+$")
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

    local isGardenPlant = (recordId:find("^hw_plant_") ~= nil)

    -- Guard: prevent double-harvest while plant is hidden / on respawn timer.
    -- (plant is still technically activatable at scale 0.001)
    if isGardenPlant then
        local existing = plant_objects[recordId]
        if existing and not existing.shown then
            sendMsg(actor, "This plant has not grown back yet.")
            return
        end
    end

    -- Grant ingredient
    giveItem(actor, cfg.item, 1)

    -- Garden plants: remove from world and start real-time respawn timer.
    -- Mushrooms (forest) don't hide — they just give an item with a storage cooldown.
    if isGardenPlant and worldObject then
        local pos, cell_name
        pcall(function()
            pos       = worldObject.position
            cell_name = worldObject.cell and worldObject.cell.name or ""
        end)
        plant_objects[recordId] = {
            recordId = recordId,
            position = pos,
            cellName = cell_name,
            readyAt  = realTimeAccum + PLANT_RESPAWN_REAL,
            shown    = false,
        }
        hideObject(worldObject, actor)
    elseif not isGardenPlant then
        -- Mushrooms: use storage cooldown (game-time, safe via getGameTime())
        local now = getGameTime()
        local key = "harvest_" .. recordId
        G:set(key, now + (cfg.respawn or SECS_PER_HOUR * 24))
    end

    local displayName = isGardenPlant
        and getPlantDisplayName(recordId)
        or (cfg.item:gsub("hw_", ""):gsub("_", " "))
    sendMsg(actor, "You have successfully harvested " .. displayName .. ".")
end

-- ---------------------------------------------------------------------------
-- Tree chopping
-- ---------------------------------------------------------------------------

local function handleTree(recordId, objectId, actor)
    local cfg = TREE_CFG[recordId]
    if not cfg then return end

    local now  = getGameTime()
    local readyKey = "tree_ready_" .. objectId
    local readyAt  = G:get(readyKey) or 0

    if now < readyAt then
        local daysLeft = math.ceil((readyAt - now) / (24 * SECS_PER_HOUR))
        sendMsg(actor, "This tree has not grown back yet. (~" .. daysLeft .. " day(s) remaining)")
        return
    end

    local wpnId = getEquippedWeaponId(actor)
    if not wpnId or not AXE_IDS[wpnId] then
        sendMsg(actor, "You need an axe equipped to chop this tree.")
        return
    end

    local axeSkill = getSkill(actor, "axe")
    local power    = WEAPON_POWER[wpnId] or 1.0
    local damage   = math.max(1, math.floor(axeSkill * 0.08 + power))

    local hpKey = "tree_hp_" .. objectId
    local hp    = G:get(hpKey) or cfg.base_hp

    hp = hp - damage
    trainSkill(actor, "axe", 0.05)

    if hp <= 0 then
        local logs     = math.random(1, math.max(1, math.floor(power * 1.5)))
        local branches = math.random(1, math.max(1, math.floor(power * 2) + 1))
        giveItem(actor, "hw_log",    logs)
        giveItem(actor, "hw_branch", branches)

        G:set(readyKey, now + cfg.respawn)
        G:set(hpKey,    cfg.base_hp)

        sendMsg(actor,
            "The tree falls! You get " .. logs .. " log(s) and "
            .. branches .. " branch(es). (Axe skill: " .. math.floor(axeSkill) .. ")")
    else
        G:set(hpKey, hp)
        sendMsg(actor,
            "You chop the tree. (" .. hp .. " HP left; Axe skill: "
            .. math.floor(axeSkill) .. "; damage: " .. damage .. ")")
    end
end

-- ---------------------------------------------------------------------------
-- Mining
-- ---------------------------------------------------------------------------

local function handleMineral(recordId, objectId, actor)
    local cfg = MINERAL_CFG[recordId]
    if not cfg then return end

    local depKey = "depleted_" .. objectId
    if G:get(depKey) then
        sendMsg(actor, "This deposit is depleted. Use the Mine Management Board to refresh.")
        return
    end

    local wpnId = getEquippedWeaponId(actor)
    if not wpnId or not PICKAXE_IDS[wpnId] then
        sendMsg(actor, "You need a pickaxe equipped to mine this.")
        return
    end

    local bluntSkill = getSkill(actor, "bluntweapon")
    local power      = WEAPON_POWER[wpnId] or 1.0
    local chance     = math.min(0.92, 0.25 + (bluntSkill / 100) * 0.65 + (power - 1) * 0.1)

    trainSkill(actor, "bluntweapon", 0.08)

    if math.random() < chance then
        local amount  = math.max(1, math.floor(1 + power * 0.5 + bluntSkill * 0.02))
        if bluntSkill >= 40 and math.random() < 0.25 then
            amount = amount + 1
        end

        giveItem(actor, cfg.item, amount)
        G:set(depKey, true)

        local label = cfg.item:gsub("hw_", ""):gsub("_", " ")
        sendMsg(actor,
            "You mine " .. amount .. " " .. label .. ". "
            .. "(Blunt skill: " .. math.floor(bluntSkill) .. ")")
    else
        sendMsg(actor,
            "Your pick glances off the rock. Try again. "
            .. "(Blunt skill: " .. math.floor(bluntSkill) .. ")")
    end
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
-- Door teleportation
-- ---------------------------------------------------------------------------

local function handleDoor(recordId, actor)
    local dest = DOOR_DESTINATIONS[recordId]
    if not dest then return end

    if dest.require then
        local inv = types.Actor.inventory(actor)
        if inv:countOf(dest.require) == 0 then
            sendMsg(actor, dest.locked_msg or "You need a pass to enter here.")
            return
        end
    end

    local cell = world.getCellByName(dest.cell)
    if not cell then
        sendMsg(actor, "Error: destination cell '" .. dest.cell .. "' not found.")
        return
    end

    world.teleportActor(
        actor, cell,
        util.vector3(dest.x, dest.y, dest.z),
        util.vector3(0, 0, 0))
end

-- ---------------------------------------------------------------------------
-- Main event dispatcher
-- ---------------------------------------------------------------------------

local function onHW_Activate(data)
    local rid   = data.recordId
    local oid   = data.objectId
    local actor = data.actor
    local obj   = data.object   -- world-object ref (may be nil for older saves)

    local ok, err = pcall(function()
        if HARVEST_CFG[rid] then
            handlePlant(rid, actor, obj)
        elseif TREE_CFG[rid] then
            handleTree(rid, oid, actor)
        elseif MINERAL_CFG[rid] then
            handleMineral(rid, oid, actor)
        elseif rid == "hw_bed" then
            handleBed(actor)
        elseif rid == "hw_mine_refresh_station" then
            handleMineRefresh(actor)
        elseif rid == "hw_vending_machine_garden" then
            handleGardenVendor(actor)
        elseif DOOR_DESTINATIONS[rid] then
            handleDoor(rid, actor)
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
        for id in pairs(MINERAL_CFG) do
            local gen = (G:get("mine_generation") or 0) + 1
            G:set("mine_generation", gen)
            break
        end
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
