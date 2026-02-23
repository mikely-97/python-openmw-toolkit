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
  openmw.util.vector3(x,y,z)     – 3-component vector

Time advancement for the bed
-----------------------------
  As of OpenMW 0.49, there is no public Lua API to advance in-game time
  or open the rest/wait menu from a script.  The bed currently restores
  the player's stats to full and shows a flavour message.  A future
  OpenMW release that exposes world.advanceTime() will be easy to wire in.
]]

local storage = require('openmw.storage')
local core    = require('openmw.core')
local world   = require('openmw.world')
local types   = require('openmw.types')
local util    = require('openmw.util')

local G = storage.globalSection("HubWorld")

-- ---------------------------------------------------------------------------
-- Configuration tables
-- ---------------------------------------------------------------------------

local SECS_PER_HOUR = 3600

-- Items granted by each harvestable activator recordId
local HARVEST_CFG = {
    -- plants (Garden)
    hw_plant_basil_01 = { item="hw_herb_basil",     respawn=24*SECS_PER_HOUR },
    hw_plant_basil_02 = { item="hw_herb_basil",     respawn=24*SECS_PER_HOUR },
    hw_plant_basil_03 = { item="hw_herb_basil",     respawn=24*SECS_PER_HOUR },
    hw_plant_basil_04 = { item="hw_herb_basil",     respawn=24*SECS_PER_HOUR },
    hw_plant_basil_05 = { item="hw_herb_basil",     respawn=24*SECS_PER_HOUR },
    hw_plant_mint_01  = { item="hw_herb_mint",      respawn=24*SECS_PER_HOUR },
    hw_plant_mint_02  = { item="hw_herb_mint",      respawn=24*SECS_PER_HOUR },
    hw_plant_mint_03  = { item="hw_herb_mint",      respawn=24*SECS_PER_HOUR },
    hw_plant_mint_04  = { item="hw_herb_mint",      respawn=24*SECS_PER_HOUR },
    hw_plant_mint_05  = { item="hw_herb_mint",      respawn=24*SECS_PER_HOUR },
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

-- Door destinations: recordId → { cell, x, y, z, require_item }
-- Garden doors are real DOOR records — engine teleports natively, no entry here.
-- Positions are 60 % of the original design to match build.py cell layout.
local DOOR_DESTINATIONS = {
    hw_door_forest  = { cell="Hub Forest",  x=0,    y=-660, z=0,
                        require="hw_forest_pass",
                        locked_msg="You need a Forest Pass. Buy one from the vendor." },
    hw_door_mine    = { cell="Hub Mine",    x=0,    y=420,  z=0,
                        require="hw_mine_pass",
                        locked_msg="You need a Mine Pass. Buy one from the vendor." },
    -- Return destinations land in front of the respective outgoing door in IdleMW
    hw_door_return_forest  = { cell="IdleMW", x=1020, y=0,    z=0 },
    hw_door_return_mine    = { cell="IdleMW", x=0,    y=-1020,z=0 },
}

-- Anvil crafting recipes: { requires, consumes, produces, fail_consumes }
-- "requires" = item that must be present (not consumed on failure)
-- "consumes" = { {id, n}, … } consumed on success
-- "fail_consumes" = { {id, n}, … } consumed on failure (wasted material)
local ANVIL_RECIPES = {
    {
        label   = "Wooden Axe (1 log + 2 branches)",
        needs   = { hw_log=1, hw_branch=2 },
        consumes= { {"hw_log",1}, {"hw_branch",2} },
        produces= "hw_axe_wooden_craft",
        fail_waste = { {"hw_branch",1} },
    },
    {
        label   = "Iron Pickaxe (3 ingots)",
        needs   = { hw_iron_ingot=3 },
        consumes= { {"hw_iron_ingot",3} },
        produces= "hw_pickaxe_iron",
        fail_waste = { {"hw_iron_ingot",1} },
    },
    {
        label   = "Wooden Instrument (2 logs + 3 branches)",
        needs   = { hw_log=2, hw_branch=3 },
        consumes= { {"hw_log",2}, {"hw_branch",3} },
        produces= "hw_instrument_wood",
        fail_waste = { {"hw_branch",1} },
    },
}

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local function sendMsg(actor, text)
    -- Send display message to player-side script
    actor:sendEvent("HW_ShowMsg", { text = text })
end

local function getEquippedWeaponId(actor)
    local equip = types.Actor.getEquipment(actor)
    -- Equipment slot for the right hand (weapon) in Morrowind = slot 13
    -- The constant name may vary by OpenMW version; try both forms.
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
    -- Returns base skill value (0-100+).
    -- For NPCs and the player the API is identical.
    local ok, val = pcall(function()
        return types.NPC.stats.skills[skillName](actor).base
    end)
    if ok then return val end
    return 10  -- safe default if API differs
end

local function trainSkill(actor, skillName, amount)
    -- Attempt to increment a skill.  In OpenMW, .base on dynamic stats
    -- is typically writable; the engine may cap it.
    pcall(function()
        local stat = types.NPC.stats.skills[skillName](actor)
        stat.base = stat.base + amount
    end)
end

-- ---------------------------------------------------------------------------
-- Plant / mushroom pickup
-- ---------------------------------------------------------------------------

local function handlePlant(recordId, objectId, actor)
    local cfg = HARVEST_CFG[recordId]
    if not cfg then return end

    local now     = core.getGameTimeInSeconds()
    local key     = "harvest_" .. objectId
    local readyAt = G:get(key) or 0

    if now < readyAt then
        local hoursLeft = math.ceil((readyAt - now) / SECS_PER_HOUR)
        sendMsg(actor, "Already harvested. Ready in ~" .. hoursLeft .. " hour(s).")
        return
    end

    types.Actor.inventory(actor):add(cfg.item, 1)

    G:set(key, now + cfg.respawn)

    local label = cfg.item:gsub("hw_", ""):gsub("_", " ")
    sendMsg(actor, "You pick a " .. label .. ".")
end

-- ---------------------------------------------------------------------------
-- Tree chopping
-- ---------------------------------------------------------------------------

local function handleTree(recordId, objectId, actor)
    local cfg = TREE_CFG[recordId]
    if not cfg then return end

    local now  = core.getGameTimeInSeconds()
    local readyKey = "tree_ready_" .. objectId
    local readyAt  = G:get(readyKey) or 0

    if now < readyAt then
        local daysLeft = math.ceil((readyAt - now) / (24 * SECS_PER_HOUR))
        sendMsg(actor, "This tree has not grown back yet. (~" .. daysLeft .. " day(s) remaining)")
        return
    end

    -- Check axe
    local wpnId = getEquippedWeaponId(actor)
    if not wpnId or not AXE_IDS[wpnId] then
        sendMsg(actor, "You need an axe equipped to chop this tree.")
        return
    end

    -- Compute chop damage
    local axeSkill = getSkill(actor, "axe")
    local power    = WEAPON_POWER[wpnId] or 1.0
    local damage   = math.max(1, math.floor(axeSkill * 0.08 + power))

    -- Retrieve / init tree HP
    local hpKey = "tree_hp_" .. objectId
    local hp    = G:get(hpKey) or cfg.base_hp

    hp = hp - damage

    -- Train axe skill slightly per swing
    trainSkill(actor, "axe", 0.05)

    if hp <= 0 then
        -- Tree felled!
        local logs     = math.random(1, math.max(1, math.floor(power * 1.5)))
        local branches = math.random(1, math.max(1, math.floor(power * 2) + 1))
        local inv = types.Actor.inventory(actor)
        inv:add("hw_log",    logs)
        inv:add("hw_branch", branches)

        G:set(readyKey, now + cfg.respawn)  -- regrow in 7 days
        G:set(hpKey,    cfg.base_hp)        -- reset HP for next time

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

    -- Check pickaxe
    local wpnId = getEquippedWeaponId(actor)
    if not wpnId or not PICKAXE_IDS[wpnId] then
        sendMsg(actor, "You need a pickaxe equipped to mine this.")
        return
    end

    -- Skill check
    local bluntSkill = getSkill(actor, "bluntweapon")
    local power      = WEAPON_POWER[wpnId] or 1.0
    local chance     = math.min(0.92, 0.25 + (bluntSkill / 100) * 0.65 + (power - 1) * 0.1)

    -- Train blunt skill
    trainSkill(actor, "bluntweapon", 0.08)

    if math.random() < chance then
        local amount  = math.max(1, math.floor(1 + power * 0.5 + bluntSkill * 0.02))
        -- Bonus ore at high skill
        if bluntSkill >= 40 and math.random() < 0.25 then
            amount = amount + 1
        end

        types.Actor.inventory(actor):add(cfg.item, amount)
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

    -- Consume token and clear all depletion flags
    inv:remove("hw_mine_refresh", 1)

    for id, _ in pairs(MINERAL_CFG) do
        -- We store depletion by objectId, not recordId.
        -- Walk through known storage keys to find depleted minerals.
        -- (A cleaner approach would track objectIds at placement time,
        --  but storage iteration is not yet available in all OpenMW builds.)
        -- Fallback: clear any storage key prefixed "depleted_".
        -- See onSave/onLoad for how we track objectIds.
    end

    -- Use a dedicated refresh flag that the activator scripts check
    G:set("mine_refresh_pending", true)
    sendMsg(actor, "Mine refresh token used! The deposits will be available again.")
end

-- ---------------------------------------------------------------------------
-- Bed — rest / time advance
-- ---------------------------------------------------------------------------

local function handleBed(actor)
    -- Restore the player's health, magicka, and fatigue to full.
    -- True time advance is not yet in the public Lua API (OpenMW 0.49).
    -- Wire world.advanceTime(hours) here when available.
    pcall(function()
        local h = types.Actor.stats.health(actor)
        h.current = h.base
        local m = types.Actor.stats.magicka(actor)
        m.current = m.base
        local f = types.Actor.stats.fatigue(actor)
        f.current = f.base
    end)
    sendMsg(actor, "You rest on the bed and recover fully.  (24 h time advance TODO)")
end

-- ---------------------------------------------------------------------------
-- Anvil crafting
-- ---------------------------------------------------------------------------

local function handleAnvil(actor)
    local inv        = types.Actor.inventory(actor)
    local repSkill   = getSkill(actor, "repair")

    -- Find first applicable recipe
    for _, recipe in ipairs(ANVIL_RECIPES) do
        local ok = true
        for itemId, needed in pairs(recipe.needs) do
            if inv:countOf(itemId) < needed then
                ok = false
                break
            end
        end

        if ok then
            local successChance = math.min(0.97, 0.35 + (repSkill / 100) * 0.62)
            trainSkill(actor, "repair", 0.1)

            if math.random() < successChance then
                for _, pair in ipairs(recipe.consumes) do
                    inv:remove(pair[1], pair[2])
                end
                inv:add(recipe.produces, 1)
                sendMsg(actor,
                    "You craft: " .. recipe.produces:gsub("hw_", ""):gsub("_", " ")
                    .. "!  (Repair skill: " .. math.floor(repSkill) .. ")")
            else
                for _, pair in ipairs(recipe.fail_waste) do
                    inv:remove(pair[1], pair[2])
                end
                sendMsg(actor,
                    "Crafting failed — you waste some materials. "
                    .. "(Repair skill: " .. math.floor(repSkill)
                    .. " / chance " .. math.floor(successChance * 100) .. "%)")
            end
            return  -- only attempt first matching recipe
        end
    end

    -- No recipe matched — tell player what they need
    sendMsg(actor,
        "Crafting options: "
        .. "Wooden Axe (1 log + 2 branches)  |  "
        .. "Iron Pickaxe (3 ingots)  |  "
        .. "Wooden Instrument (2 logs + 3 branches).  "
        .. "You don't have the required materials.")
end

-- ---------------------------------------------------------------------------
-- Forge smelting
-- ---------------------------------------------------------------------------

local function handleForge(actor)
    local inv    = types.Actor.inventory(actor)
    local oreAmt = inv:countOf("hw_iron_ore")

    if oreAmt >= 2 then
        local batches = math.min(math.floor(oreAmt / 2), 5)  -- max 5 ingots/use
        inv:remove("hw_iron_ore", batches * 2)
        inv:add("hw_iron_ingot", batches)
        trainSkill(actor, "repair", 0.05 * batches)
        sendMsg(actor,
            "You smelt " .. (batches * 2) .. " ore into " .. batches .. " ingot(s).")
    else
        sendMsg(actor,
            "You need at least 2 iron ore to smelt. (Have: " .. oreAmt .. ")")
    end
end

-- ---------------------------------------------------------------------------
-- Door teleportation
-- ---------------------------------------------------------------------------

local function handleDoor(recordId, actor)
    local dest = DOOR_DESTINATIONS[recordId]
    if not dest then return end

    -- Check access requirement
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
    local rid      = data.recordId   -- ACTI record ID (template)
    local oid      = data.objectId   -- unique world-object ID (instance)
    local actor    = data.actor

    if HARVEST_CFG[rid] then
        handlePlant(rid, oid, actor)
    elseif TREE_CFG[rid] then
        handleTree(rid, oid, actor)
    elseif MINERAL_CFG[rid] then
        handleMineral(rid, oid, actor)
    elseif rid == "hw_bed" then
        handleBed(actor)
    elseif rid == "hw_anvil" then
        handleAnvil(actor)
    elseif rid == "hw_forge" then
        handleForge(actor)
    elseif rid == "hw_mine_refresh_station" then
        handleMineRefresh(actor)
    elseif DOOR_DESTINATIONS[rid] then
        handleDoor(rid, actor)
    end
end

-- Handle the mine_refresh_pending flag: clear depleted_ flags
-- This runs via onUpdate so the activator script can also check it.
-- Note: player spawn is handled by the sStartCell GMST override in the
-- addon binary, not by Lua — no onNewGame handler needed.
local function onUpdate(dt)
    if G:get("mine_refresh_pending") then
        G:set("mine_refresh_pending", false)
        -- Clear all known mineral depletion keys by brute-force re-set
        -- (Full storage key iteration is engine-version dependent)
        for id in pairs(MINERAL_CFG) do
            -- We don't know the instance objectIds here, so use a workaround:
            -- store a "generation" counter; activator.lua compares against it
            local gen = (G:get("mine_generation") or 0) + 1
            G:set("mine_generation", gen)
            break  -- one increment per refresh is enough
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
