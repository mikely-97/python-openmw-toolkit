--[[
hub_world/data/scripts/hub/player.lua
PLAYER script — displays messages and handles player-side UI.

Receives events from the GLOBAL script:
  HW_ShowMsg    { text = "..." }     – show a HUD notification message
  HW_Countdown  { timeLeft = N }     – garden respawn countdown
      N > 0  : seconds remaining (shown as MM:SS in yellow)
      N == 0 : all plants ready  (shown as "Ready!" in green)
      N < 0  : player not in garden (hide the widget)
]]

local ui   = require('openmw.ui')
local util = require('openmw.util')

-- ---------------------------------------------------------------------------
-- HUD message
-- ---------------------------------------------------------------------------

local function onHW_ShowMsg(data)
    if data and data.text then
        ui.showMessage(data.text)
    end
end

-- ---------------------------------------------------------------------------
-- Garden countdown widget
-- Big yellow MM:SS (or green "Ready!") shown when player is in Hub Garden.
-- ---------------------------------------------------------------------------

local countdownWidget = nil

local function destroyCountdown()
    if countdownWidget then
        pcall(function() countdownWidget:destroy() end)
        countdownWidget = nil
    end
end

local function setCountdown(text, color)
    if countdownWidget then
        local ok = pcall(function()
            countdownWidget:update { props = { text = text, textColor = color } }
        end)
        if ok then return end
        destroyCountdown()
    end

    pcall(function()
        countdownWidget = ui.create {
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

local function onHW_Countdown(data)
    if not data or data.timeLeft == nil then return end

    local t = data.timeLeft

    if t < 0 then
        destroyCountdown()
        return
    end

    if t == 0 then
        setCountdown("Ready!", util.color.rgba(0.2, 0.9, 0.2, 1.0))
    else
        local m = math.floor(t / 60)
        local s = math.floor(t % 60)
        setCountdown(
            string.format("%02d:%02d", m, s),
            util.color.rgba(1.0, 0.85, 0.0, 1.0)
        )
    end
end

-- ---------------------------------------------------------------------------
-- Export
-- ---------------------------------------------------------------------------

return {
    eventHandlers = {
        HW_ShowMsg   = onHW_ShowMsg,
        HW_Countdown = onHW_Countdown,
    },
}
