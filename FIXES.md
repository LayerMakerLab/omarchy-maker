# Fixes, with evidence

Test machine: MacBookPro13,3 (Intel i7-6700HQ, AMD Radeon Pro 4xx, 2880x1800 at scale 2), Omarchy 4.0.3,
Hyprland 0.56.2 (Lua config), OrcaSlicer 2.4.2 and Bambu Studio 02.08.02.61 from their official
Ubuntu 24.04 AppImages. Tests were driven from ssh with `wtype`, `hyprctl` and a virtual pointer,
screenshots with `grim`. Dates are 2026-09-14.

## 1. Certificate prompt on every launch

**Symptom.** Both slicers open with a dialog: "use system SSL certificate:
/etc/ssl/certs/ca-certificates.crt. To manually specify the system certificate store, set the
SSL_CERT_FILE environment variable ... Do you want to continue?" It comes back on every launch
unless "Remember my choice" is ticked.

**Fix.** `maker-run` exports `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` when it is unset
and the file exists.

**Checked.** Launched each app with and without the variable: the dialog appears without it and
does not appear with it. Through the installed launcher the running OrcaSlicer process carries
`SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`.

## 2. AppImages need FUSE 2

**Symptom.** Omarchy ships `fuse3` but not `fuse2`, so an AppImage cannot mount itself.

**Fix.** `maker install` runs the AppImage with `--appimage-extract` and keeps the unpacked tree
under `~/.local/share/omarchy-maker/apps/<app>/<version>`, with `current` pointing at the newest.

## 3. OrcaSlicer: Ctrl+Shift+G traps the cursor

**Symptom** ([OrcaSlicer #15338](https://github.com/OrcaSlicer/OrcaSlicer/issues/15338), reported on
Omarchy 4.0.0). In Preview, Ctrl+Shift+G opens the print dialog and the "Jump to layer" popup at the
same time. With Omarchy's `follow_mouse = 1`, every mouse movement snaps the cursor back.

**Cause.** Two key handlers both take the shortcut (upstream fix proposed in
[PR #15551](https://github.com/OrcaSlicer/OrcaSlicer/pull/15551)); focus-follows-mouse turns the
double popup into a trap.

**Fix.** `hypr/maker.lua`: `o.window("^(orca-slicer)$", { no_follow_mouse = true })`. Omarchy ships
the same rule for JetBrains IDEs in `default/hypr/apps/jetbrains.lua`.

**Checked.** Fresh OrcaSlicer window each run, cube sliced, Ctrl+Shift+G in Preview, then four
relative pointer movements of (-60, +40):

| | `hyprctl getprop ... no_follow_mouse` | cursor after each movement |
|---|---|---|
| without `hypr.maker` | false | 720,463 · 720,463 · 660,503 · 720,463 (snaps back) |
| with `hypr.maker` | true | 660,500 · 600,540 · 540,580 · 480,620 (moves) |

## 4. Double-clicking a model file

**Symptom.** GIO resolves `model/3mf` to `org.gnome.Nautilus.desktop`, so a double-click opens the
file manager: shared-mime-info makes 3MF a subclass of `application/zip`, which Nautilus lists. `model/stl` has no default.

**Fix.** When no default was chosen in any `mimeapps.list`, the installer sets 3MF to Bambu Studio
and STL/STEP/OBJ to OrcaSlicer (or whichever of the two is installed). `maker default` changes it;
uninstall restores what was there.

**Checked.** `gio open cube20.3mf` starts Bambu Studio through the maker launcher with the file
loaded.

## 5. Bambu Studio: dragging a file in crashes it

**Symptom** ([Bambu Studio #12052](https://github.com/bambulab/BambuStudio/issues/12052)). Dropping a
.3mf from the file manager kills Bambu Studio with SIGSEGV.

**Cause.** Bambu Studio always runs under XWayland (it ignores `GDK_BACKEND=wayland`). Hyprland's
XWayland bridge answers the drop's `text/uri-list` request with the clipboard contents instead of
the file ([Hyprland discussion 11179](https://github.com/hyprwm/Hyprland/discussions/11179), open since
2025-07, still present in 0.56.2), and Bambu Studio passes that text to `load_files` unchecked.

**Checked.**

| | result |
|---|---|
| clipboard holds text, drag .3mf into Bambu Studio | SIGSEGV; core frames `bambu-studio+0x5d402a1`, `+0x20a467a`, the same offsets as the upstream report; Omarchy shows "Process crashed: bambu-studio" |
| `wl-copy --clear`, same drag | file loads |
| clipboard holds text, same drag into OrcaSlicer (native Wayland) | file loads |

**Workaround.** Files that do not arrive by drag-and-drop never touch that path. The installer turns
on Bambu Studio's `single_instance` setting, so double-click, Open With and `maker open` hand the file
to the window that is already open. Checked: with Bambu Studio running, `gio open` on a second .3mf
starts no new process and the file loads in the open window. `maker doctor` prints a reminder.

A drop target inside the Omarchy shell was tried as a safe landing spot and does not work: the
Quickshell `DropArea` receives the drag (enter, formats, proposed action) but never the drop, which
matches a report about a Qt app in the same Hyprland discussion.

**Real fix.** Upstream, in either Hyprland (the bridge) or Bambu Studio (validate the dropped
paths). Not done here.

## 6. Printer camera: "missing H.264 codecs for GStreamer"

**Symptom.** In OrcaSlicer's Device tab, starting a Bambu printer's camera shows: "Your system is
missing H.264 codecs for GStreamer, which are required to play video. (Try installing the
gstreamer1.0-plugins-bad or gstreamer1.0-libav packages, then restart Orca Slicer?)"

**Cause.** Omarchy 4.0.3 installs `gstreamer` and `gst-plugins-base` only; `avdec_h264` (gst-libav)
and `h264parse` (gst-plugins-bad) are missing.

**Fix.** `omarchy pkg add gst-libav gst-plugins-good gst-plugins-bad`, then restart the slicer.
`maker doctor` checks for both elements and prints that command. (The Debian package names in
Orca's message do not exist on Arch.)

**Checked.** 2026-09-14 on the Omarchy box: before, the error above for Jr. (P1S); after installing
the three packages (1.28.6-3, matching the installed gstreamer) and restarting Orca, the camera
plays ("Playing...") and shows the plate.

## Not reproduced

- **Bambu Studio Preferences tabs do not switch** ([#12063](https://github.com/bambulab/BambuStudio/issues/12063)):
  the tabs work in the official AppImage. The report used the Flatpak, which Omarchy does not ship.
- **OrcaSlicer only partly fits on screen** ([#11316](https://github.com/OrcaSlicer/OrcaSlicer/issues/11316),
  Omarchy 3.1.6, OrcaSlicer 2.3.1): OrcaSlicer 2.4.2 on a scale-2 screen with `GDK_SCALE=2` draws at
  the right size.
- **Bambu Studio drawn twice as large** under `GDK_SCALE=2` (the AUR package, per bist.be): the
  AppImage under XWayland draws at the right size.

## 7. OrcaSlicer swapped out on a laptop with zram

**Symptom.** Rotating or zooming a model stutters after Orca has sat idle for a while.

**Cause.** Omarchy runs zram swap with `vm.swappiness = 150`; on a 16 GB MacBook Pro the kernel had pushed
566 MB of a running Orca (RSS 1.9 GB) into zram while Samba, Codex and friends held memory (2026-09-16,
`/proc/<pid>/status` VmSwap).

**Fix.** `maker-run` starts the slicers in a systemd user scope with `MemorySwapMax=0` and `CPUWeight=300`
when `systemd-run --user --scope` works, so their pages stay in RAM and they win the CPU under contention.
Applied to the running Orca with `systemctl --user set-property --runtime <scope> MemorySwapMax=0`.

## 8. Maker apps tiled on top of each other

**Symptom.** A Blender or OpenSCAD opened next to Orca took half of Orca's window; Blender's Preferences
and render result windows were tiled too, and its file browser came up 320 x 240.

**Fix.** `hypr/maker.lua`: window rules give each main window a workspace (Bambu Studio 7, OpenSCAD 8,
Blender 9, OrcaSlicer 10) and float Blender's pop-ups at 1200 x 780. Blender 5.2 renames those windows a
moment after creating them ("File Browser" becomes "Blender File View", "Image Editor" becomes "Blender
Render"), so the rule matches `initial_title`; a rule on the final title never applied and the windows stayed
at Blender's 320 x 240 whatever size the rule asked for (checked both ways with real key presses).

## 9. OpenSCAD's AppImage on Wayland

**Symptom.** With Omarchy's `QT_QPA_PLATFORM=wayland;xcb` the AppImage prints `Could not find the Qt platform
plugin "wayland"` and falls back to XWayland at 1x, tiny on a scale-2 screen.

**Cause.** The AppImage bundles Qt 6.2.4 without the Wayland platform plugin.

**Fix.** `maker-run openscad` sets `QT_QPA_PLATFORM=xcb` and `QT_SCALE_FACTOR=$GDK_SCALE` (Omarchy's
`xwayland.force_zero_scaling` leaves scaling to the app). Checked with a screenshot at 2880 x 1800: crisp,
and the preview renders with OpenCSG on the Radeon in 6 ms.

## 10. The Orca keys took Blender's

**Symptom.** Ctrl+Alt+Space (full screen area) and Ctrl+Alt+S (save a copy) in Blender opened the Orca
menu and the process picker instead.

**Fix.** Every Orca key checks the window in front: Orca gets maker-orca, any other app gets the same chord
re-sent with `send_shortcut`. Proven with Blender's own event log (`blender --debug-events`) receiving
LEFT_CTRL, LEFT_ALT, S and opening its file browser.

## 11. Do not record the screen with gpu-screen-recorder on the 2016 MacBook Pro

**Symptom.** A full-screen `gpu-screen-recorder -w screen -q high` run (44 s, 2880 x 1800, 30 fps) turned
the screen black after about a minute. Ping still answered; hyprctl, ps and pgrep hung; new logins hung.

**Cause.** The kernel log shows a GPU job timeout on the Radeon Pro (Baffin) followed by amdgpu's own
recovery getting stuck in `dm_suspend` during the ASIC reset, with Hyprland blocked in
`amdgpu_ctx_mgr_entity_flush` behind it. Once the reset workqueue is wedged nothing in userspace can free it.

**Recovery.** A synced reboot over ssh through SysRq (`s`, `u`, `b` into `/proc/sysrq-trigger`) rather than
the power button, because the shared disk hangs off this machine. Unsaved slicer work is lost either way.

**Rule.** No KMS screen capture on this hardware. Demo material is stills from `grim` (which never touched
the driver in two days of use), or a phone pointed at the screen.

