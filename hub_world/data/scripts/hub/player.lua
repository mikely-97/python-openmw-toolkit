--[[
hub_world/data/scripts/hub/player.lua
PLAYER script — displays messages and handles player-side UI.

Receives events from the GLOBAL script:
  HW_ShowMsg  { text = "..." }        – show a HUD notification message
  HW_TalkTo   { vendor = <object> }   – open dialogue/barter with an NPC
]]

local ui = require('openmw.ui')

local function onHW_ShowMsg(data)
    if data and data.text then
        ui.showMessage(data.text)
    end
end

return {
    eventHandlers = {
        HW_ShowMsg = onHW_ShowMsg,
    },
}
