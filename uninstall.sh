#!/bin/bash
# uninstall.sh — take omarchy-maker back out. The slicers' own settings in ~/.config stay.
#
#   ./uninstall.sh              remove everything maker added, including the apps it downloaded
#   ./uninstall.sh --keep-apps  keep the unpacked AppImages
#   ./uninstall.sh --purge      also delete your printer list (~/.config/omarchy-maker/printers.json)
#   ./uninstall.sh --dry-run
set -uo pipefail

MAKER_HOME=${MAKER_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-maker}
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
DRY=0 KEEP_APPS=0 PURGE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --keep-apps) KEEP_APPS=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
note() { printf '  %s\n' "$*"; }
act() { if [ "$DRY" -eq 1 ]; then note "would $*"; return 1; fi; return 0; }

echo "Removing omarchy-maker"

# file types: put back what they opened in before, or drop maker's line when nothing did
MIMEAPPS="$CONFIG_HOME/mimeapps.list"
if [ -f "$MAKER_HOME/state/mime-before" ]; then
  while IFS='=' read -r type before; do
    [ -n "$type" ] || continue
    current=$(awk -v t="$type" -F= '/^\[/{sec=$0} sec=="[Default Applications]" && $1==t {sub(/;.*/, "", $2); print $2; exit}' "$CONFIG_HOME/mimeapps.list" 2>/dev/null)
    case "$current" in BambuStudio.desktop|com.orcaslicer.OrcaSlicer.desktop) ;; *) continue ;; esac
    if [ -n "$before" ] && [ "$before" != "$current" ] && [ "$before" != org.gnome.Nautilus.desktop ]; then
      act "set $type back to $before" && gio mime "$type" "$before" >/dev/null 2>&1 && note "$type opens in ${before%.desktop} again"
    elif [ -f "$MIMEAPPS" ]; then
      act "remove the $type default from $MIMEAPPS" && sed -i "\#^$type=\(BambuStudio\|com\.orcaslicer\.OrcaSlicer\)\.desktop;\?\$#d" "$MIMEAPPS" && note "$type default removed"
    fi
  done < "$MAKER_HOME/state/mime-before"
fi

# launchers maker wrote (a stock launcher without the marker is left alone)
for entry in BambuStudio.desktop com.orcaslicer.OrcaSlicer.desktop; do
  f="$DATA_HOME/applications/$entry"
  if grep -q '^X-OmarchyMaker=1' "$f" 2>/dev/null && act "remove $f"; then rm -f "$f" && note "removed $f"; fi
done
command -v update-desktop-database >/dev/null && [ "$DRY" -eq 0 ] && update-desktop-database -q "$DATA_HOME/applications" 2>/dev/null

# Printers widget: out of the bar, then off the disk (printers.json goes with the maker config below)
PLUGIN="$CONFIG_HOME/omarchy/plugins/layermaker.printers"
if [ -d "$PLUGIN" ] && act "remove the Printers widget"; then
  if [ -z "${MAKER_NO_SHELL:-}" ] && command -v omarchy >/dev/null && grep -q '"layermaker.printers"' "$CONFIG_HOME/omarchy/shell.json" 2>/dev/null; then
    omarchy plugin disable layermaker.printers >/dev/null 2>&1
  fi
  rm -rf "$PLUGIN"
  [ -z "${MAKER_NO_SHELL:-}" ] && command -v omarchy-shell >/dev/null && omarchy-shell shell rescanPlugins >/dev/null 2>&1
  note "Printers widget removed"
fi

# Omarchy menu block
MENU="$CONFIG_HOME/omarchy/extensions/omarchy-menu.jsonc"
if grep -q 'omarchy-maker:begin' "$MENU" 2>/dev/null && act "remove the 3D Printing entries from $MENU"; then
  sed -i '/omarchy-maker:begin/,/omarchy-maker:end/d' "$MENU" && note "menu entries removed"
fi

# Hyprland rules
HYPR="$CONFIG_HOME/hypr"
if grep -q 'require("hypr.maker")' "$HYPR/hyprland.lua" 2>/dev/null && act "remove the hypr.maker require"; then
  sed -i '/require("hypr.maker")/d' "$HYPR/hyprland.lua"
  # drop the blank line install.sh put in front of it, when it is now the last line
  [ -z "$(tail -n 1 "$HYPR/hyprland.lua")" ] && sed -i '$ d' "$HYPR/hyprland.lua"
  note "hyprland.lua no longer requires hypr.maker"
fi
if [ -f "$HYPR/maker.lua" ] && act "remove $HYPR/maker.lua"; then rm -f "$HYPR/maker.lua" && note "removed $HYPR/maker.lua"; fi

# commands, then the program and (unless kept) the apps
for tool in maker maker-run maker-bambu maker-orca maker-meshy; do
  link="$HOME/.local/bin/$tool"
  if [ -L "$link" ] && [[ "$(readlink "$link")" == "$MAKER_HOME"/* ]] && act "remove $link"; then rm -f "$link" && note "removed $link"; fi
done
if [ -d "$MAKER_HOME" ]; then
  if [ "$KEEP_APPS" -eq 1 ]; then
    act "remove $MAKER_HOME except apps/" && { rm -rf "${MAKER_HOME:?}/src" "${MAKER_HOME:?}/state" "${MAKER_HOME:?}/cache" "${MAKER_HOME:?}/bin"; note "kept $MAKER_HOME/apps"; }
  else
    act "remove $MAKER_HOME" && { rm -rf "$MAKER_HOME"; note "removed $MAKER_HOME"; }
  fi
fi
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/omarchy-maker"
if [ -f "$CACHE_DIR/orca-layout.json" ] && act "remove $CACHE_DIR/orca-layout.json"; then
  rm -f "$CACHE_DIR/orca-layout.json"
  note "removed what the Orca keys remembered about Orca's layout"
fi
if compgen -G "$CACHE_DIR/meshy-*.log" >/dev/null && act "remove the Meshy run logs in $CACHE_DIR"; then
  rm -f "$CACHE_DIR"/meshy-*.log && note "removed the Meshy run logs (your models stay in ~/Projects/3D_Exports/meshy)"
fi
[ -d "$CACHE_DIR" ] && rmdir "$CACHE_DIR" 2>/dev/null
if [ -d "$CONFIG_HOME/omarchy-maker" ]; then
  if [ "$PURGE" -eq 1 ]; then
    act "remove $CONFIG_HOME/omarchy-maker" && { rm -rf "$CONFIG_HOME/omarchy-maker"; note "removed $CONFIG_HOME/omarchy-maker"; }
  else
    act "remove $CONFIG_HOME/omarchy-maker/config" && rm -f "$CONFIG_HOME/omarchy-maker/config"
    [ -f "$CONFIG_HOME/omarchy-maker/printers.json" ] && note "kept your printer list in $CONFIG_HOME/omarchy-maker/printers.json (--purge deletes it)"
    [ -f "$CONFIG_HOME/omarchy-maker/orca-setups.json" ] && note "kept your Orca setups in $CONFIG_HOME/omarchy-maker/orca-setups.json (--purge deletes it)"
    rmdir "$CONFIG_HOME/omarchy-maker" 2>/dev/null
  fi
fi
echo "Done."
