# Why makers

Picked 2026-09-14 after the AI-desk idea (omarchy prettyness) turned out to be crowded and
partly shipped by Omarchy 4 itself. Every number below was pulled on 2026-09-14; the commands
are at the bottom so they can be re-run.

## What is crowded

GitHub repositories matching `omarchy` plus a keyword (name, description, topics):

| keyword | repos |
|---|---|
| (none) | 12,091 |
| theme | 2,431 |
| plugin | 1,924 |
| widget | 1,118 |
| dotfiles | 667 |
| agent | 390 |
| ai | 303 |
| claude | 140 |

The plugin marketplace (`omacom/omarchy-plugin-marketplace`, `registry.json`) lists 3,150
plugins from 3,148 repos, all added between 2026-07-28 and 2026-09-14, most of them after
Omarchy 4.0.0 shipped the plugin system on 2026-08-14.

## What is empty

| keyword | repos |
|---|---|
| freecad | 0 |
| blender | 0 |
| orcaslicer | 0 |
| kicad | 0 |
| klipper | 1 |
| prusa | 1 |
| cad | 2 |
| slicer | 2 |
| octoprint | 3 |
| bambu | 5 |

Omarchy's own source has no mention of OrcaSlicer, Bambu Studio, PrusaSlicer, FreeCAD,
OpenSCAD, KiCad or Blender (GitHub code search in `omacom/omarchy`).

Maker plugins in the marketplace: two Bambu Lab widgets, two OctoPrint widgets, one Prusa
Connect widget and one MakerWorld widget. Stars on 2026-09-14: 3, 2, 2, 0, 0, 0. Nothing for
Klipper/Moonraker, nothing for slicers or CAD. For scale, the popular plugins from the same
weeks: omamail 231, omarchy-pods 198, blip 155, omarchy-time-machine 106.

## The pain is real and recent

Bug reports that name Omarchy, per tracker: OrcaSlicer 9, Bambu Studio 6, FreeCAD 4,
PrusaSlicer 1 (Hyprland: 39, 21, 53, 7). Open ones from the last month:

- OrcaSlicer #15338 (2026-08-23, Omarchy 4.0.0): Ctrl+Shift+G in Preview opens two popups and,
  with Omarchy's default focus-follows-mouse, the cursor snaps back and cannot leave them.
- Bambu Studio #12052 (2026-08-27, Omarchy 4.0.1): dragging a .3mf into the window segfaults
  whenever the clipboard is not empty. Cause: Hyprland's XWayland selection bridge hands the
  drop the clipboard text instead of the file URI (hyprwm/Hyprland discussion 11179).
- Bambu Studio #12063 (2026-08-28, Omarchy Quattro): the Preferences panel and MakerWorld
  online pages do not work. Bambu's reply: Wayland and Hyprland are not tested.
- OrcaSlicer #11316 (Omarchy 3.1.6): only part of the window fits on screen. Omarchy exports
  `GDK_SCALE` for HiDPI screens (`~/.config/hypr/monitors.lua`) and wxWidgets apps scale twice.

## The bet, and the risk

The bet: a maker who opens Omarchy should get slicers and CAD that work on the first launch,
their printers in the bar (Klipper included), and model files that open from the file manager.
Nobody packages that today.

The risk: the printer widgets that exist got almost no stars, so Omarchy's current users are not
asking for one more widget. The pull has to come from "my slicer finally works" and from makers
outside Omarchy, not from the bar.

## Re-running the numbers

```bash
gh api -X GET search/repositories -f q='omarchy freecad' --jq .total_count
gh api repos/omacom/omarchy-plugin-marketplace/contents/registry.json -H 'Accept: application/vnd.github.raw' | jq '.sources | length'
gh api -X GET search/issues -f q='omarchy repo:OrcaSlicer/OrcaSlicer' --jq .total_count
gh api -X GET search/code -f q='orcaslicer repo:omacom/omarchy' --jq .total_count
```
