# Lua Scripting Reference

Lua scripts are **not stored in the addon binary**. They are loose `.lua` files
registered by a `.omwscripts` manifest file.

## Script types

| Type   | Flag        | Always active?  | World write? | Key APIs                  |
|--------|-------------|-----------------|--------------|---------------------------|
| GLOBAL | `GLOBAL`    | Yes             | Yes          | openmw.world              |
| MENU   | `MENU`      | Yes (pre-game)  | No           | openmw.ui, openmw.input   |
| PLAYER | `PLAYER`    | On player       | No           | openmw.ui, openmw.nearby  |
| LOCAL  | `NPC` etc.  | When loaded     | No           | openmw.nearby (read-only) |
| CUSTOM | `CUSTOM`    | When attached   | No           | openmw.nearby (read-only) |

## .omwscripts format

```
# Comment
GLOBAL: scripts/mymod/global.lua
PLAYER: scripts/mymod/player.lua
NPC, CREATURE: scripts/mymod/actor_ai.lua
CUSTOM: scripts/mymod/attachable.lua
```

Register in `openmw.cfg` as a separate line: `content=mymod.omwscripts`

## Script template

```lua
local core = require('openmw.core')
local self = require('openmw.self')   -- LOCAL/PLAYER only

local function onInit(data)        end   -- first time only
local function onSave()            return {} end
local function onLoad(data)        end
local function onUpdate(dt)        end   -- every frame

-- LOCAL/CUSTOM: called when THIS object is activated.
-- KEY must be "onActivated" — "onActivate" is silently ignored.
local function onActivated(actor)  end

return {
    engineHandlers = {
        onInit      = onInit,
        onSave      = onSave,
        onLoad      = onLoad,
        onUpdate    = onUpdate,
        onActivated = onActivated,
    }
}
```

**Activation handler names:**

| Script type | Handler key   | Signature         |
|-------------|---------------|-------------------|
| LOCAL/CUSTOM | `onActivated` | `function(actor)` |
| GLOBAL      | use `sendGlobalEvent` + `eventHandlers` — no built-in activation handler |

## Key API packages

| Package          | Available in     | Purpose                                    |
|------------------|------------------|--------------------------------------------|
| `openmw.core`    | all              | sendGlobalEvent, getGameTime, types        |
| `openmw.world`   | GLOBAL only      | createObject, remove, teleport, getPlayer  |
| `openmw.nearby`  | LOCAL/PLAYER     | objects in loaded range                    |
| `openmw.self`    | LOCAL/PLAYER     | the object this script runs on             |
| `openmw.ui`      | PLAYER/MENU      | widgets, text, HUD                         |
| `openmw.storage` | all              | persist tables across sessions             |
| `openmw.types`   | all              | Actor, NPC, Weapon, … type-specific methods|
| `openmw.util`    | all              | math, vectors, transforms                  |
| `openmw.async`   | all              | timers, coroutines (not in GLOBAL, 0.50)   |
| `openmw.vfs`     | all              | read VFS data files                        |
| `openmw.ambient` | PLAYER           | ambient sound                              |
| `openmw.animation`| LOCAL/PLAYER    | animation playback                         |

## Recipes

### LOCAL activator → GLOBAL event pattern

```lua
-- activator.lua  (LOCAL, on ACTI objects)
local self_m = require('openmw.self')
local core   = require('openmw.core')
local types  = require('openmw.types')

local function onActivated(actor)
    -- filter for our records
    if not MY_IDS[self_m.object.recordId] then return end
    -- ignore non-player activations
    local ok, isPlayer = pcall(function() return types.Actor.isPlayer(actor) end)
    if ok and isPlayer == false then return end

    core.sendGlobalEvent("MyMod_Activate", {
        recordId = self_m.object.recordId,
        object   = self_m.object,
        actor    = actor,
    })
end

return {
    engineHandlers = { onActivated = onActivated },
}

-- global.lua  (GLOBAL)
local world = require('openmw.world')
local types = require('openmw.types')

local function onMyModActivate(data)
    -- mutate world here
    data.actor:sendEvent("MyMod_ShowMsg", { text = "Hello!" })
end

return { eventHandlers = { MyMod_Activate = onMyModActivate } }

-- player.lua  (PLAYER)
local ui = require('openmw.ui')
local function onMyModShowMsg(data)
    if data and data.text then ui.showMessage(data.text) end
end
return { eventHandlers = { MyMod_ShowMsg = onMyModShowMsg } }
```

### Give / take items (GLOBAL only)

```lua
-- Give N items to an actor
local function giveItem(actor, id, count)
    for i = 1, math.max(1, count) do
        -- count=1 avoids gold denomination lookup (createObject(id, N>1) → looks for "gold_00N")
        world.createObject(id, 1):moveInto(types.Actor.inventory(actor))
    end
end

-- Take items from an actor
local function takeItem(actor, id, count)
    local stack = types.Actor.inventory(actor):find(id)
    if stack then stack:remove(count or 1) end
end
```

### Spawn / respawn a world object (GLOBAL only)

```lua
-- Hide: remove the object, save position for later.
-- Object properties (position/rotation/scale) are READ-ONLY — only remove works.
local savedInfo = {
    recordId = obj.recordId,
    cellName = obj.cell.name,   -- store string, not cell reference (avoids stale refs)
    position = obj.position,
}
obj:remove()

-- Respawn: createObject starts disabled; teleport places + enables atomically.
-- world.placeNewObject is a no-op in OpenMW 0.50 — don't use it.
local newObj = world.createObject(savedInfo.recordId, 1)
newObj:teleport(savedInfo.cellName, savedInfo.position)
-- cellName can be a plain string; no getCellByName() needed.
```

### Real-time respawn timer (GLOBAL onUpdate)

```lua
local realTimeAccum = 0.0
local pending = {}   -- rid → { recordId, cellName, position, readyAt }

local function onUpdate(dt)
    realTimeAccum = realTimeAccum + dt
    for rid, info in pairs(pending) do
        if realTimeAccum >= info.readyAt then
            pending[rid] = nil
            local ok, err = pcall(function()
                world.createObject(info.recordId, 1):teleport(info.cellName, info.position)
            end)
            if not ok then
                local pok, player = pcall(function() return world.getPlayer() end)
                if pok and player then
                    player:sendEvent("MyMod_ShowMsg", { text = "[RESPAWN ERR] " .. tostring(err) })
                end
            end
        end
    end
end
```

### Persist data across saves

```lua
local storage = require('openmw.storage')
local section = storage.globalSection("MyMod_State")

local function onSave()  section:set("myValue", 42)  end
local function onLoad()  local v = section:get("myValue")  end
```

### HUD countdown widget (PLAYER)

```lua
local ui   = require('openmw.ui')
local util = require('openmw.util')

local widget = nil

local function setCountdown(text, color)
    if widget then pcall(function() widget:update { props = { text=text, textColor=color } } end)
    else
        pcall(function()
            widget = ui.create {
                layer = 'HUD',
                type  = ui.TYPE.Text,
                props = {
                    text             = text,
                    textColor        = color,
                    textSize         = 40,
                    relativePosition = util.vector2(0.5, 0.06),
                    anchor           = util.vector2(0.5, 0.5),
                },
            }
        end)
    end
end

local function onMyMod_Countdown(data)
    if not data or data.timeLeft == nil then return end
    local t = data.timeLeft
    if t < 0 then
        if widget then pcall(function() widget:destroy() end); widget = nil end
    elseif t == 0 then
        setCountdown("Ready!", util.color.rgba(0.2, 0.9, 0.2, 1.0))
    else
        local m, s = math.floor(t/60), math.floor(t%60)
        setCountdown(string.format("%02d:%02d", m, s), util.color.rgba(1.0, 0.85, 0.0, 1.0))
    end
end

return { eventHandlers = { MyMod_Countdown = onMyMod_Countdown } }
```
