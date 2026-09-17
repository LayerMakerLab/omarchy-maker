# Roadmap

## 0.1 (done, 2026-09-14)
- [x] OrcaSlicer and Bambu Studio from official releases, unpacked, updatable
- [x] certificate prompt, cursor trap, file types, drag-and-drop workaround (FIXES.md)
- [x] Omarchy menu entries, `maker doctor`, uninstall that restores what it changed
- [x] smoke test: install, use and uninstall in a throwaway HOME

## 0.2: printers in the bar
- [x] Omarchy shell plugin: a bar pill with the active print (progress, +N others) and a panel with
      every printer, notifications when a print finishes, fails or is cancelled (2026-09-14)
- [x] Klipper/Moonraker, checked live in the Omarchy shell against a simulated printer
- [x] `maker printer add|list|remove|test|demo`
- [ ] a physical Klipper printer (or the virtual-klipper-printer container, which needs Docker running)
- [ ] OctoPrint and PrusaLink
- [x] Bambu Lab over LAN, watch only: `maker-bambu` (MQTT over TLS, standard library, pinned
      certificate), `maker printer add-bambu|discover`; live on a P1S and an A1 (2026-09-14)
- [ ] watch a Bambu print in progress end to end (progress, time left, finished notification)
- [ ] Jr. (P1S with AMS): needs its access code from the printer screen
- [ ] screenshots on a clean workspace

## 0.2: OrcaSlicer from the keyboard
- [x] Orca mode on SUPER + ALT + O (Hyprland submap, one key then back): pages 1-6, printer, filament,
      process and plate type pickers in the Omarchy menu, slice, print, export, search, preferences
      (2026-09-15; picks checked against Orca's settings file, pages against the selected tab)
- [x] `maker-orca`: Tesseract reads Orca's lists, wlrctl clicks, a wlrctl build with a mouse-wheel action
- [x] faster (2026-09-15): tab, heading and list positions remembered; open lists told from pixels; a
      list read once, then picks read only what is on screen. Page 1.0 s to 0.5 s, cached pick 9.5 s to about 2 s
- [x] setups (printer + filament + process + plate type in one pick) and a Space menu with everything
- [x] Orca keys instead of Orca mode (2026-09-16): every maker key is Control + Alt + one key, no sticky mode,
      no timer, no cheat sheet flicker; Orca's own single-letter tools are never swallowed and Esc closes pop-ups
      (Orca's own key; a real-key test showed its dialogs answer it when they hold the focus, so the binding only
      hands Esc on when the main window holds it). Slice, export, search and preferences are Orca's own Ctrl keys
- [ ] vendor submenus (Bambu >, Generic >): picking inside one works on a freshly started Orca, but
      the next pick silently fails and can leave the list open until Orca restarts (Orca 2.4.2, GTK on
      Wayland chained popups). Not offered until that is solved
- [x] `o` puts a model on the plate, handed to the running Orca over its own D-Bus listener: no file
      window, nothing typed (2026-09-15; Orca's GTK file window ignores Return sent by wtype)
- [x] `m` makes a model with Meshy (text, a picture, 2-4 views), checks and repairs it, sizes it and puts
      it on the plate; `maker-meshy`, tested end to end against `tests/fake_meshy.py` and once for real
- [x] `g` picks the printer inside Orca's print window (slicing first if needed), confirmed in Orca's log,
      with Orca's verdict and a plate photo for LAN printers; Send stays manual (2026-09-15; Ctrl+Shift+G
      also opens "Jump to layer" in Preview, which keeps the print window from taking clicks, so `g` clicks
      Print plate instead)
- [x] plates `[` / `]` (2026-09-15): Orca has no key for plates, so `maker-orca plate next|prev` clicks the
      thumbnail next to the teal-bordered one in Preview's plate list, checks the border moved and goes
      back to the page you were on; it only acts when the list shows exactly Orca's plate count (from the log)
- [x] `t` gets the plate ready for a test print (2026-09-15): auto orient, infill down to 10% in gyroid,
      cross hatch or adaptive cubic, no brim (Orca's Auto adds one under small footprints), then slice and
      add supports only when Orca says the model has floating regions, and then the least that still prints:
      tree (auto) + critical regions only, 0.35 g against 2.48 g on the turtle, falling back to the whole tree
      if something still floats; `prep --revert` puts the five settings back (Orca has no undo for settings).
      Measured: the threshold angle at 45 deg makes more support, not less, so the preset's angle is left alone.
      Checked on the turtle: 29 s from the preset state, warning gone, supports 0.35 g
- [x] fewer supports, and only from the plate (2026-09-15): `t` weighs what the model needs (tree + on build
      plate only + critical regions only, then slice) instead of trusting Orca's overhang warning, which fires
      for overhangs Orca prints fine; it only tries another way up when support is real, and keeps the turn only
      when it weighs less (Orca's auto orient turned a 0.00 g turtle into a 0.35 g one). Supports never stand on
      the model: if that is the only way, it says so and stops. `maker-meshy orient` scores every way up on the
      mesh (overhang over the plate vs over the model, contact with the plate, height) and writes the turned
      copy; `m` asks Meshy for shapes that print without support unless --as-said
- [x] `maker-meshy split` cuts a model into glued parts (2026-09-15): a plane cut that clips only the triangles
      it passes through, the cut face capped by ear clipping with a bridged hole for each dowel socket, a blind
      socket either side (6 x 12 mm dowel, 0.30 mm play, the dowel written too) and every part stood on the
      plate and checked (closed, volume positive). Wizard sculpt at 150%: base + body + head, 21 s, 0 open
      edges, supports 6.04 g -> 3.80 g. `maker-meshy simplify` is separate and says what it opened, because
      snapping corners together tears a mesh that splitting keeps exact
- [x] Blender on Omarchy, in the workflow (2026-09-15): `maker-blender check|render|simplify|split|free`,
      headless with factory startup and global undo off. Every part it writes is rendered, which caught a cut
      through a skull's jaw and a staff with its crook sliced off, both reported as 0 open edges
- [ ] free a part that is sculpted against the body along its whole length (the wizard's staff leans on the
      robe): a grip tube frees a held part, but this one needs its centreline measured off the mesh, not
      guessed, or surface work rather than boolean cuts
- [ ] the rest of the wizard kit as drawn in concept pass 09: hood slipping over the body, face plate on a
      backing, cuff plaques
- [ ] OpenSCAD for the parametric connectors (dowels, pins, sockets) once the cuts are settled
- [ ] plates when the list is longer than the window (scroll the list first)
- [x] real key presses tested (2026-09-15) through a kernel-level test keyboard (uinput as root): enter, pages,
      Esc, timeout, an unbound key, o/m/Space/p menus, ] and g messages, and g end to end with a typed printer name
- [x] Meshy: Again (last words and height), Finish for cut-off jobs (`maker meshy resume`), the last height first,
      Meshy's free check no longer holds up the model (the edge count decides the repair)
- [x] experiments, judged yes or no on evidence (2026-09-15; the no branches stay unmerged as exp/*):
      - YES printer first: g on a printer whose setup does not match the sliced plate applies that setup and
        slices again (Orca refuses to send an A1 a plate sliced for a P1S)
      - YES any height from o: Meshy models go on the plate at a picked height (a sized copy)
      - YES the tool checks itself: `maker-orca selfcheck`, 11 s, found a flaky print window read on its first run
      - NO three tries at once: the three models stack on one spot (Orca centres each), 3x the credits
      - NO idea to print window: Orca raises itself when a model arrives, so automatic clicks could follow a focus
        jump; it found that bug (fixed: focus_on_activate = false for Orca)
      - NO grab from the screen: Print plus Model from a picture (newest first) already does it
- [x] speed, measured and judged yes or no (2026-09-15):
      - YES faster clicks (0.05 s settle): a pick 2 s to 1.5 s, self-check 11 s to 9 s
      - YES leaner print window reading (pixels for open and selected rows): g with the window open 1.8 s to
        1.35 s; printer switches across setups 12 of 12 (the list is read again where it is clicked)
      - YES verdict first, photo after: the answer at 1.3 s instead of 3.2 s
      - YES Meshy stream instead of polling: no 0-10 s lag at the finish, progress every 2 s (real run)
      - YES last printer first in g's menu: the same printer again is Enter
      - NO fewer triangles (Meshy remesh): a third of the triangles sliced only 8-13% faster; detail is lost
      - NO STL only from Meshy: the 99% wait stayed about 24 s
      - NO bytecode cache for maker-orca: compiling it costs 29 ms; NO faster bounds in plain Python: 0.91 s to 0.76 s
      - measured, not ours to change: Orca picks up handed-over files about once a second (its D-Bus listener
        sleeps a second between checks); Meshy's build is about 70 s including about 25 s at 99%
- [x] the Orca keys stay with Orca (2026-09-16): with another app in front the chord is re-sent to it, so Blender
      keeps Ctrl+Alt+Space, Ctrl+Alt+S and Ctrl+Alt+Q (proven in Blender's event log); the menu opens or brings
      forward Blender, OpenSCAD and Bambu Studio, so only Ctrl+Alt+O and Ctrl+Alt+Space need remembering
- [x] no tiling (2026-09-16): each maker app on a workspace of its own (Bambu 7, OpenSCAD 8, Blender 9, Orca 10),
      Blender's pop-ups float at 1200 x 780 (matched on their initial titles), Orca in a scope with swap off
- [ ] upstream: Orca's lists and boxes ignore the keyboard on Wayland; a tooltip closes an open list

## 0.3: more of the maker desk
- [x] OpenSCAD (2026-09-16): `maker install openscad` takes the daily AppImage (2026.09.12; the 2021.01 release
      and pacman's package have no Manifold), XWayland on purpose with the scale from GDK_SCALE, `.scad` opens
      in it, doctor renders a test model; preview checked on screen (OpenCSG, 6 ms)
- [ ] PrusaSlicer, FreeCAD: install and check each on Omarchy the same way
- [ ] model thumbnails in the file manager
- [ ] a fresh Omarchy account install, following the README only

## Meshy Auto Split (checked 2026-09-15)
- Meshy's own splitter cuts where a figure's parts meet and adds mortise-and-tenon connectors, 10 credits,
  about 2 minutes, and it is wired up as `maker-meshy parts NAME --by "..."`
- it only takes Meshy's own generations: our own model uploads fine (`convert`, 1 credit, succeeded in 2 s with
  a 7.5 MB STL as a data URI) but the splitter answers "Cannot determine the input model's version; pass the
  generation task id instead"
- re-generating a sculpt we already have costs the sculpt: Meshy 7 Ultra from the wizard's own renders lost the
  crisp hood edge, the teeth, the fingers on the staff and the stepped base

## Upstream (each needs Christian's go before anything is sent)
- [ ] `default/hypr/apps/orca-slicer.lua` for omacom/omarchy (the no_follow_mouse rule)
- [ ] Bambu Studio: validate dropped paths in `PlaterDropTarget::handleOnIdle` (#12052)
- [ ] Hyprland: the XWayland drop answered with clipboard data (discussion 11179)
- [ ] Omarchy: plugin hot reload keeps old code because `Qt.clearComponentCache` does not exist in
      Quickshell 0.3.1 (shell.qml `finishPluginReload`)

## 1.0
- [ ] screenshots (in progress 2026-09-17, taken on the laptop through its own Claude session)
- [ ] a short demo recording of the two keys: Ctrl+Alt+O, Ctrl+Alt+Space, a model in, a test-print prep, the print window
- [ ] the public repository: github.com/LayerMakerLab/omarchy-maker (name free, checked 2026-09-17; waits for Christian's GO).
      `main` is the working line; what ships is the `public` branch, one commit per release from `tools/cut-release.sh`,
      which refuses to cut anything with a private address, serial or key in it
- [ ] the wizard kit on MakerWorld and Printables, pointing back here
