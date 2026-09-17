#!/bin/bash
# install.sh — set up omarchy-maker for this user. Safe to run again.
#
#   ./install.sh                     launchers, window rules, menu entries; asks which slicers to install
#   ./install.sh --apps orca,bambu,openscad   also download the official AppImages (or --apps none)
#   ./install.sh --default-3mf bambu --default-model orca
#   ./install.sh --dry-run           say what would change, change nothing
#
# Everything lands in your home directory. Nothing needs sudo.
set -uo pipefail

ROOT=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
MAKER_HOME=${MAKER_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-maker}
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
BIN_DIR="$HOME/.local/bin"
DRY=0 APPS="" DEF3MF="" DEFMODEL="" DO_MENU=1 DO_HYPR=1

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --apps) APPS=${2:?}; shift ;;
    --apps=*) APPS=${1#*=} ;;
    --default-3mf) DEF3MF=${2:?}; shift ;;
    --default-model) DEFMODEL=${2:?}; shift ;;
    --no-menu) DO_MENU=0 ;;
    --no-hypr) DO_HYPR=0 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

note() { printf '  %s\n' "$*"; }
act() { if [ "$DRY" -eq 1 ]; then note "would $*"; return 1; fi; return 0; }

echo "omarchy-maker $(cat "$ROOT/VERSION")"
[ -r "${OMARCHY_PATH:-/usr/share/omarchy}/version" ] || note "Omarchy not found; installing the launchers anyway (window rules and menu entries need Omarchy 4)"
for tool in curl jq; do command -v "$tool" >/dev/null || { echo "missing $tool: sudo pacman -S $tool" >&2; exit 1; }; done

# 1. the program itself
echo "Program"
if act "copy $ROOT to $MAKER_HOME/src"; then
  mkdir -p "$MAKER_HOME/src"
  if [ "$ROOT" != "$MAKER_HOME/src" ]; then
    if command -v rsync >/dev/null; then rsync -a --delete --exclude .git "$ROOT/" "$MAKER_HOME/src/"
    else rm -rf "$MAKER_HOME/src" && mkdir -p "$MAKER_HOME/src" && (cd "$ROOT" && tar --exclude .git -cf - .) | (cd "$MAKER_HOME/src" && tar -xf -); fi
  fi
  note "installed copy in $MAKER_HOME/src"
fi
for tool in maker maker-run maker-bambu maker-orca maker-meshy maker-blender; do
  if act "link $BIN_DIR/$tool"; then
    mkdir -p "$BIN_DIR" && ln -sfn "$MAKER_HOME/src/bin/$tool" "$BIN_DIR/$tool" && note "$BIN_DIR/$tool"
  fi
done
MAKER="$MAKER_HOME/src/bin/maker"
[ "$DRY" -eq 1 ] && MAKER="$ROOT/bin/maker"

# 2. Hyprland window rules
if [ "$DO_HYPR" -eq 1 ]; then
  echo "Hyprland"
  HYPR="$CONFIG_HOME/hypr"
  if [ ! -f "$HYPR/hyprland.lua" ]; then
    note "no $HYPR/hyprland.lua (not Omarchy 4); skipped"
  else
    if ! cmp -s "$ROOT/hypr/maker.lua" "$HYPR/maker.lua" && act "write $HYPR/maker.lua"; then
      cp "$ROOT/hypr/maker.lua" "$HYPR/maker.lua" && note "window rules in $HYPR/maker.lua"
    fi
    if grep -q 'require("hypr.maker")' "$HYPR/hyprland.lua"; then
      note "hyprland.lua already requires hypr.maker"
    elif act "append require(\"hypr.maker\") to $HYPR/hyprland.lua"; then
      printf '\nrequire("hypr.maker")   -- omarchy-maker window rules\n' >> "$HYPR/hyprland.lua"
      note "hyprland.lua requires hypr.maker"
    fi
  fi
fi

# 2b. Orca keys (Control + Alt + one key): maker-orca clicks through wlrctl, a build with a mouse-wheel action
if [ "$DO_HYPR" -eq 1 ]; then
  echo "Orca keys"
  WLRCTL="$MAKER_HOME/bin/wlrctl"
  if [ -x "$WLRCTL" ] && grep -aq 'wheel needs NOTCHES' "$WLRCTL"; then
    note "wlrctl with the wheel action in $WLRCTL"
  elif [ -n "${MAKER_NO_BUILD:-}" ]; then
    note "skipped building wlrctl (MAKER_NO_BUILD)"
  elif act "build wlrctl into $MAKER_HOME/bin (git clone from git.sr.ht)"; then
    mkdir -p "$MAKER_HOME/state"
    if bash "$ROOT/tools/build-wlrctl.sh" "$MAKER_HOME/bin" > "$MAKER_HOME/state/wlrctl-build.log" 2>&1; then
      note "built $WLRCTL"
    else
      note "could not build wlrctl ($MAKER_HOME/state/wlrctl-build.log); the Orca keys for pages and presets need it"
    fi
  fi
  command -v grim >/dev/null || note "the Orca keys need grim: sudo pacman -S grim"
  command -v tesseract >/dev/null || note "the Orca keys need Tesseract: sudo pacman -S tesseract tesseract-data-eng"
fi

# 3. Omarchy menu: Install > 3D Printing, Setup > 3D Printing, Update > Slicers
if [ "$DO_MENU" -eq 1 ]; then
  echo "Omarchy menu"
  MENU="$CONFIG_HOME/omarchy/extensions/omarchy-menu.jsonc"
  if [ ! -d "$CONFIG_HOME/omarchy" ]; then
    note "no $CONFIG_HOME/omarchy; skipped"
  elif act "add the 3D Printing entries to $MENU"; then
    mkdir -p "$(dirname "$MENU")"
    [ -s "$MENU" ] || printf '{\n}\n' > "$MENU"
    tmp=$(mktemp)
    # drop an older copy of the block, then insert the current one before the last closing brace
    sed '/omarchy-maker:begin/,/omarchy-maker:end/d' "$MENU" > "$tmp"
    last=$(grep -n '^[[:space:]]*}[[:space:]]*$' "$tmp" | tail -1 | cut -d: -f1)
    if [ -z "$last" ]; then
      note "could not find the closing brace in $MENU; left alone"
    else
      { head -n $((last - 1)) "$tmp"; cat "$ROOT/omarchy/menu.jsonc"; tail -n +"$last" "$tmp"; } > "$tmp.new"
      if cmp -s "$tmp.new" "$MENU"; then note "menu entries already current"; else cat "$tmp.new" > "$MENU"; note "Install > 3D Printing, Setup > 3D Printing, Update > Slicers"; fi
    fi
    rm -f "$tmp" "$tmp.new"
  fi
fi

# 4. the Printers widget (stays out of the bar until a printer is added)
if [ -d "$CONFIG_HOME/omarchy" ]; then
  echo "Printers widget"
  if act "copy the Printers widget to $CONFIG_HOME/omarchy/plugins/layermaker.printers"; then
    "$MAKER" plugin-install && note "installed; it joins the bar when you run: maker printer add NAME URL"
  fi
fi

# 5. slicers
echo "Slicers"
if [ -z "$APPS" ] && [ -t 0 ] && command -v gum >/dev/null; then
  APPS=$(gum choose --no-limit --header "Install which apps? (space to pick, enter to go)" "OrcaSlicer" "Bambu Studio" "OpenSCAD" | sed 's/OrcaSlicer/orca/; s/Bambu Studio/bambu/; s/OpenSCAD/openscad/' | paste -sd, -)
fi
for app in ${APPS//,/ }; do
  case "$app" in
    none) ;;
    orca|bambu|openscad) if act "download and unpack $app"; then "$MAKER" install "$app" || note "$app did not install; see above"; fi ;;
    *) note "unknown app '$app' (orca, bambu, openscad)" ;;
  esac
done
# launchers with the fixes for apps that came from pacman or the AUR
for app in orca bambu openscad; do
  if "$MAKER" has "$app" 2>/dev/null && [ ! -L "$MAKER_HOME/apps/$app/current" ]; then
    if act "write a fixed launcher for the system $app"; then "$MAKER" entry "$app" && note "launcher for the system $app"; fi
  fi
done

# 6. file types: only fill in types nobody claimed yet (or that open in the file manager)
echo "File types"
if command -v gio >/dev/null; then
  claim() {  # $1 kind (3mf|model) $2 app $3 mime type to inspect
    local current; current=$("$MAKER" explicit-default "$3")
    case "$current" in
      ""|org.gnome.Nautilus.desktop)
        if act "open $1 files in $2"; then "$MAKER" default "$1" "$2" | sed 's/^/  /'; fi ;;
      *) note "$3 already opens in ${current%.desktop}; left alone" ;;
    esac
  }
  if [ -n "$DEF3MF" ]; then act "open 3mf files in $DEF3MF" && "$MAKER" default 3mf "$DEF3MF" | sed 's/^/  /'
  elif "$MAKER" has bambu 2>/dev/null; then claim 3mf bambu model/3mf
  elif "$MAKER" has orca 2>/dev/null; then claim 3mf orca model/3mf; fi
  if [ -n "$DEFMODEL" ]; then act "open model files in $DEFMODEL" && "$MAKER" default model "$DEFMODEL" | sed 's/^/  /'
  elif "$MAKER" has orca 2>/dev/null; then claim model orca model/stl
  elif "$MAKER" has bambu 2>/dev/null; then claim model bambu model/stl; fi
fi

echo
if [ "$DRY" -eq 1 ]; then echo "Dry run: nothing changed."; exit 0; fi
"$MAKER" doctor
