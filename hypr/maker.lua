-- omarchy-maker: window rules and keys for maker apps on Omarchy 4 (Hyprland Lua).
-- Required once from ~/.config/hypr/hyprland.lua by install.sh; removed by uninstall.sh.

-- OrcaSlicer: Ctrl+Shift+G in Preview opens the print dialog and the "Jump to layer" popup
-- together, and with focus-follows-mouse the cursor snaps back on every movement
-- (OrcaSlicer #15338). Same rule Omarchy ships for JetBrains IDEs.
-- A model handed to a running Orca (Ctrl+Alt+I, or a Meshy model landing) makes Orca raise itself; with Omarchy's
-- focus_on_activate that pulls you out of whatever you were typing in. Omarchy turns it off per app the same way
-- (default/hypr/apps/telegram.lua). New Orca windows still get the focus.
o.window("^(orca-slicer)$", { no_follow_mouse = true, focus_on_activate = false })

-- No tiling for the maker apps. Every one of them gets a workspace of its own, so a new window never halves
-- the one you are working in (a Blender or OpenSCAD opened next to Orca took half of it). Only the main window
-- is placed; dialogs follow their parent. Ctrl+Alt+O and the Ctrl+Alt+Space menu bring each app forward, so
-- there is no workspace number to remember. Orca is matched on its class alone: its main window is created with an
-- empty title (checked after a reboot: a title rule left it on workspace 1), and its dialogs follow it anyway.
o.window({ class = "^(orca-slicer)$" }, { workspace = "10" })     -- Orca's window has no title yet when it is placed
o.window({ class = "^(bambu-studio)$" }, { workspace = "7" })
o.window({ class = "^(blender)$", title = ".*- Blender [0-9].*" }, { workspace = "9" })
o.window({ class = "^(OpenSCAD|org.openscad.openscad)$", title = ".*OpenSCAD$" }, { workspace = "8" })
-- Blender 5.2 opens Preferences, the render result and the file browser as windows of their own. Tiled, they
-- halve the workspace; left alone, the file browser comes up 320 x 240. Matched on the titles they are created
-- with (they are renamed a moment later: "File Browser" becomes "Blender File View", "Image Editor" becomes
-- "Blender Render"), so the size applies at creation. 1200 x 780 logical on a 1440 x 900 screen at scale 2.
o.window({ class = "^(blender)$", initial_title = "^(Preferences|Image Editor|File Browser)$" }, { float = true, center = true, size = { 1200, 780 } })

-- Orca keys. Everything omarchy-maker adds to OrcaSlicer is Control + Alt + one key (Control + Option on an
-- Apple keyboard), pressed with Orca in front; Ctrl+Alt+O works from anywhere and brings Orca forward. Orca's own
-- shortcuts are Ctrl, Ctrl+Shift, single letters, arrows, Tab and Esc (Help > Keyboard Shortcuts,
-- KBShortcutsDialog.cpp in Orca 2.4.2) and never Ctrl+Alt; Omarchy has only Ctrl+Alt+Delete and Ctrl+Alt+Tab.
-- So the two sets never mix: there is no mode to be in or out of, no timer, and Orca's m, r, s, f and 1-9 always
-- mean what Orca says. With another app in front the chord is handed to that app untouched, because Blender has
-- Ctrl+Alt+Space (full screen area), Ctrl+Alt+S (save a copy) and Ctrl+Alt+Q (quad view) of its own.
--   Ctrl+Alt+O      OrcaSlicer: open it, or bring it forward (from anywhere)
--   Ctrl+Alt+Space  one menu with everything below, plus your setups and every preset read so far
--   Ctrl+Alt+1..6   Home  Prepare  Preview  Device  Project  Calibration
--   Ctrl+Alt+I      put a model on the plate (your Meshy models, Downloads, 3D_Exports, Orca's recent projects)
--   Ctrl+Alt+M      make a model with Meshy (maker-meshy, ~/.config/meshy/env)
--   Ctrl+Alt+P      printer, or a whole setup (~/.config/omarchy-maker/orca-setups.json)
--   Ctrl+Alt+F      filament preset          Ctrl+Alt+S  process preset (the slicing profile)
--   Ctrl+Alt+B      bed: the plate type
--   Ctrl+Alt+G      print: Orca's print window, pick the printer (you press Send)
--   Ctrl+Alt+T      get the plate ready for a test print (lay it down, 10% infill, no brim, supports if Orca asks)
--   Ctrl+Alt+K      cut a model into parts that slot together (Blender) and put them all on the plate
--   Ctrl+Alt+V      speeds: a touch off every printing speed, bridges slower still (maker-orca speeds --revert)
--   Ctrl+Alt+[ ]    previous / next plate (Orca has no key for plates; picked in Preview's plate list)
--   Ctrl+Alt+H      show these keys
--   Esc             Orca's own: closes the pop-up in front. When Orca's main window holds the focus while a pop-up
--                   is up (a menu or a click can leave it that way), Esc is handed to the pop-up instead.
-- Slice, export, search and preferences are Orca's own Ctrl+R, Ctrl+G, Ctrl+F and Ctrl+P: nothing to add.
-- Pages and presets go through maker-orca, which clicks Orca's tabs and lists for you (on Wayland they only take
-- the mouse) and checks in Orca's settings that the choice took.
local maker_orca = (os.getenv("HOME") or "") .. "/.local/bin/maker-orca"
local maker_run = (os.getenv("HOME") or "") .. "/.local/bin/maker-run"
local orca_class = "orca-slicer"

-- Orca's main window is the one whose title ends with "- OrcaSlicer" (even when Omarchy's pop-out floats it);
-- every other orca-slicer window is a pop-up: a dialog, a print window, a warning.
local function is_orca_main(window)
  return window.class == orca_class and window.title ~= nil and window.title:sub(-12) == "- OrcaSlicer"
end

local function orca_windows()
  local main, popups = nil, {}
  for _, window in ipairs(hl.get_windows()) do
    if window.class == orca_class then
      if is_orca_main(window) then main = window else table.insert(popups, window) end
    end
  end
  return main, popups
end

-- One of the Orca keys: maker-orca with Orca in front, the chord itself to any other app in front.
local function orca(key, args)
  return function()
    local active = hl.get_active_window()
    if active and active.class ~= orca_class then
      hl.dispatch(hl.dsp.send_shortcut({ mods = "CTRL ALT", key = key }))
      return
    end
    hl.exec_cmd(maker_orca .. " " .. args)
  end
end

local function open_orca()
  local main = orca_windows()
  if main then
    hl.dispatch(hl.dsp.focus({ window = main }))
  else
    hl.exec_cmd("uwsm-app -- " .. maker_run .. " orca")
  end
end

-- Esc stays Orca's key (non-consuming: it always reaches the window that has the focus). Orca's pop-ups close on
-- it themselves; only when the main window holds the focus with a pop-up still up does maker-orca hand it on.
local function escape_to_popup()
  local active = hl.get_active_window()
  if not active or not is_orca_main(active) then
    return
  end
  local _, popups = orca_windows()
  if #popups > 0 then
    hl.exec_cmd(maker_orca .. " dismiss")
  end
end

o.bind("CTRL + ALT + O", "OrcaSlicer: open it, or bring it forward", open_orca)
o.bind("CTRL + ALT + SPACE", "Orca: one menu with everything", orca("SPACE", "menu"))
for number, page in ipairs({ "Home", "Prepare", "Preview", "Device", "Project", "Calibration" }) do
  o.bind("CTRL + ALT + " .. number, "Orca: " .. page, orca(tostring(number), "page " .. page:lower()))
end
o.bind("CTRL + ALT + I", "Orca: put a model on the plate", orca("I", "open"))
o.bind("CTRL + ALT + M", "Orca: make a model with Meshy", orca("M", "meshy"))
o.bind("CTRL + ALT + P", "Orca: printer, or a whole setup", orca("P", "pick printer"))
o.bind("CTRL + ALT + F", "Orca: filament preset", orca("F", "pick filament"))
o.bind("CTRL + ALT + S", "Orca: process preset (the slicing profile)", orca("S", "pick process"))
o.bind("CTRL + ALT + B", "Orca: bed, the plate type", orca("B", "pick plate"))
o.bind("CTRL + ALT + G", "Orca: print, pick the printer", orca("G", "print"))
o.bind("CTRL + ALT + T", "Orca: get the plate ready for a test print", orca("T", "prep"))
o.bind("CTRL + ALT + K", "Orca: cut a model into parts that slot together", orca("K", "kit"))
o.bind("CTRL + ALT + V", "Orca: a touch off the speeds", orca("V", "speeds"))
o.bind("CTRL + ALT + BRACKETLEFT", "Orca: previous plate", orca("BRACKETLEFT", "plate prev"))
o.bind("CTRL + ALT + BRACKETRIGHT", "Orca: next plate", orca("BRACKETRIGHT", "plate next"))
o.bind("CTRL + ALT + H", "Orca: show the keys", orca("H", "hint"))
hl.bind("ESCAPE", escape_to_popup, { non_consuming = true, description = "Orca: Esc reaches the pop-up behind the main window" })
