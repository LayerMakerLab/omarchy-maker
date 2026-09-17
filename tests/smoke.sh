#!/bin/bash
# tests/smoke.sh — static checks plus a full install, use and uninstall in a throwaway HOME.
# Downloads nothing: a fake OrcaSlicer stands in for the real one.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PASS=0 FAIL=0
pass() { PASS=$((PASS + 1)); printf '  ok   %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$*"; }
check() { local what=$1; shift; if "$@" >/dev/null 2>&1; then pass "$what"; else fail "$what"; fi; }

echo "static"
for f in "$ROOT"/install.sh "$ROOT"/uninstall.sh "$ROOT"/bin/maker "$ROOT"/bin/maker-run "$ROOT"/tests/*.sh; do check "bash -n ${f#"$ROOT"/}" bash -n "$f"; done
if command -v shellcheck >/dev/null; then
  check "shellcheck" shellcheck -x -S warning "$ROOT"/install.sh "$ROOT"/uninstall.sh "$ROOT"/bin/maker "$ROOT"/bin/maker-run "$ROOT"/tests/smoke.sh
fi
check "maker-bambu parses" python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$ROOT/bin/maker-bambu"
check "maker-orca parses" python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$ROOT/bin/maker-orca"
check "maker-orca reads real Orca captures (tests/test_maker_orca.py)" python3 "$ROOT/tests/test_maker_orca.py"
check "maker-meshy parses" python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$ROOT/bin/maker-meshy"
check "maker-meshy meshes: size, standing up, watertight count (tests/test_maker_meshy.py)" python3 "$ROOT/tests/test_maker_meshy.py"
check "wlrctl wheel patch parses" python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$ROOT/tools/wlrctl-wheel.py"
check "bash -n tools/build-wlrctl.sh" bash -n "$ROOT/tools/build-wlrctl.sh"
jsonc_ok() {  # strip // comments and trailing commas, then parse
  python3 - "$1" <<'PY'
import json, re, sys
text = open(sys.argv[1]).read()
text = "\n".join(re.sub(r'^\s*//.*$', '', line) for line in text.splitlines())
text = re.sub(r',(\s*[}\]])', r'\1', text)
json.loads(text)
PY
}
command -v node >/dev/null && check "printer widget logic (node tests/model.test.js)" node "$ROOT/tests/model.test.js"
widget_version=$(jq -r .version "$ROOT/plugins/printers/manifest.json")
check "widget JS file carries the manifest version (the shell caches JS by URL)" bash -c "grep -q 'import \"Printers-$widget_version.js\" as Model' '$ROOT/plugins/printers/BarWidget.qml' && grep -q 'import \"Printers-$widget_version.js\" as Model' '$ROOT/plugins/printers/Panel.qml' && test -f '$ROOT/plugins/printers/Printers-$widget_version.js' && test \$(ls '$ROOT'/plugins/printers/*.js | wc -l) = 1"
if command -v omarchy-plugin-validate >/dev/null; then
  check "omarchy plugin validate plugins/printers" omarchy-plugin-validate "$ROOT/plugins/printers"
fi
check "menu block is valid JSONC" jsonc_ok <(printf '{\n%s\n}\n' "$(cat "$ROOT/omarchy/menu.jsonc")")

echo "install into a throwaway HOME"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
export HOME="$T/home" XDG_CONFIG_HOME="$T/home/.config" XDG_DATA_HOME="$T/home/.local/share" MAKER_NO_SHELL=1 MAKER_NO_BUILD=1
unset MAKER_HOME MAKER_CONFIG BAMBU_CONF SSL_CERT_FILE
mkdir -p "$HOME/.config/hypr" "$HOME/.config/omarchy/extensions"
printf 'require("default.hypr.omarchy")\nrequire("hypr.monitors")\n' > "$HOME/.config/hypr/hyprland.lua"
printf '{\n  // user entries\n  "personal": {"icon":"x","label":"Personal"},\n}\n' > "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
cp "$HOME/.config/hypr/hyprland.lua" "$T/hyprland.orig"; cp "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc" "$T/menu.orig"

check "dry run changes nothing" bash -c "'$ROOT/install.sh' --dry-run --apps none && cmp -s '$T/hyprland.orig' '$HOME/.config/hypr/hyprland.lua' && [ ! -e '$HOME/.local/bin/maker' ]"
"$ROOT/install.sh" --apps none > "$T/install1.log" 2>&1
"$ROOT/install.sh" --apps none > "$T/install2.log" 2>&1
check "maker linked into ~/.local/bin" test -x "$HOME/.local/bin/maker"
check "window rules written" grep -q 'no_follow_mouse' "$HOME/.config/hypr/maker.lua"
check "Orca keys written (Control + Alt, no mode)" bash -c "grep -q 'o.bind(\"CTRL + ALT + O\"' '$HOME/.config/hypr/maker.lua' && ! grep -q 'define_submap' '$HOME/.config/hypr/maker.lua'"
check "maker-orca linked into ~/.local/bin" test -x "$HOME/.local/bin/maker-orca"
check "maker-meshy linked into ~/.local/bin" test -x "$HOME/.local/bin/maker-meshy"
check "maker meshy without a key says where the key goes (and calls nothing)" bash -c "env -u MESHY_API_KEY MESHY_API_BASE=http://127.0.0.1:9 '$HOME/.local/bin/maker' meshy credits --quiet 2>&1 | grep -q 'meshy/env'"
check "Ctrl+Alt+I and Ctrl+Alt+M written" bash -c "grep -q 'orca(\"I\", \"open\")' '$HOME/.config/hypr/maker.lua' && grep -q 'orca(\"M\", \"meshy\")' '$HOME/.config/hypr/maker.lua'"
check "Ctrl+Alt+T prepares a test print" bash -c "grep -q 'orca(\"T\", \"prep\")' '$HOME/.config/hypr/maker.lua' && '$HOME/.local/bin/maker-orca' keys | grep -q 'test print'"
check "prep and its way back are in the help" bash -c "'$HOME/.local/bin/maker-orca' --help | grep -q 'prep --revert'"
check "Esc is handed to a pop-up behind Orca's main window" bash -c "grep -q 'hl.bind(\"ESCAPE\", escape_to_popup' '$HOME/.config/hypr/maker.lua'"
check "maker keys prints the Orca keys" bash -c "'$HOME/.local/bin/maker' keys | grep -q 'Ctrl+Alt+O'"
check "maker apps get their own workspaces (no tiling)" bash -c "grep -q 'class = \"^(blender)\$\", title = \".*- Blender \[0-9\].*\" }, { workspace = \"9\" }' '$HOME/.config/hypr/maker.lua' && grep -q 'workspace = \"8\"' '$HOME/.config/hypr/maker.lua'"
check "Blender's pop-ups float at a usable size" bash -c "grep -q 'initial_title = \"^(Preferences|Image Editor|File Browser)\$\" }, { float = true, center = true, size' '$HOME/.config/hypr/maker.lua'"
check "maker-run openscad says how to install it" bash -c "'$HOME/.local/bin/maker-run' openscad 2>&1 | grep -q 'maker install openscad'"
check "maker has openscad is false before an install" bash -c "! '$HOME/.local/bin/maker' has openscad"
check "maker open a .scad file asks for OpenSCAD" bash -c "touch '$T/x.scad' && '$HOME/.local/bin/maker' open '$T/x.scad' 2>&1 | grep -q 'maker install openscad'"
check "maker-orca setups explains the file when there is none" bash -c "'$HOME/.local/bin/maker-orca' setups | grep -q 'orca-setups.json'"
mkdir -p "$XDG_CONFIG_HOME/omarchy-maker"
printf '{"setups": [{"name": "Test", "printer": "P1S", "filaments": ["Bambu PLA"], "process": "0.20mm Standard @BBL X1C", "plate": "Textured PEI Plate"}]}\n' > "$XDG_CONFIG_HOME/omarchy-maker/orca-setups.json"
check "maker-orca setups lists a setup" bash -c "'$HOME/.local/bin/maker-orca' setups | grep -q 'Test.*P1S: Bambu PLA'"
mkdir -p "$HOME/.cache/omarchy-maker" && echo '{}' > "$HOME/.cache/omarchy-maker/orca-layout.json"
check "require added exactly once" test "$(grep -c 'require("hypr.maker")' "$HOME/.config/hypr/hyprland.lua")" = 1
check "menu block added exactly once" test "$(grep -c 'omarchy-maker:begin' "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc")" = 1
check "user menu entries kept" grep -q '"personal"' "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
check "menu file still valid JSONC" jsonc_ok "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"

echo "use"
MH="$XDG_DATA_HOME/omarchy-maker"
mkdir -p "$MH/apps/orca/v0.0.0-test"
cat > "$MH/apps/orca/v0.0.0-test/AppRun" <<FAKE
#!/bin/bash
printf 'SSL=%s\n' "\${SSL_CERT_FILE:-}" > "$T/fake-orca.log"
printf 'ARG=%s\n' "\$@" >> "$T/fake-orca.log"
FAKE
chmod +x "$MH/apps/orca/v0.0.0-test/AppRun"
ln -sfn v0.0.0-test "$MH/apps/orca/current"
M="$HOME/.local/bin/maker"
check "maker has orca" "$M" has orca
check "maker has bambu is false" bash -c "! '$M' has bambu"
check "maker entry orca writes a launcher" bash -c "'$M' entry orca && grep -q 'maker-run orca' '$XDG_DATA_HOME/applications/com.orcaslicer.OrcaSlicer.desktop'"
if command -v desktop-file-validate >/dev/null; then
  check "launcher passes desktop-file-validate" desktop-file-validate "$XDG_DATA_HOME/applications/com.orcaslicer.OrcaSlicer.desktop"
fi
printf 'solid x\nendsolid x\n' > "$T/part one.stl"
"$M" open "$T/part one.stl" > /dev/null
for _ in $(seq 1 30); do [ -s "$T/fake-orca.log" ] && break; sleep 0.1; done
check "maker open runs the slicer with the file" grep -qx "ARG=$T/part one.stl" "$T/fake-orca.log"
if [ -r /etc/ssl/certs/ca-certificates.crt ]; then
  check "the slicer gets SSL_CERT_FILE" grep -qx 'SSL=/etc/ssl/certs/ca-certificates.crt' "$T/fake-orca.log"
fi
check "maker open refuses a non-model" bash -c "touch '$T/notes.txt'; ! '$M' open '$T/notes.txt'"
check "no explicit default before maker sets one" test -z "$("$M" explicit-default model/stl)"
if command -v gio >/dev/null; then
  "$M" default model orca > /dev/null
  check "explicit default is OrcaSlicer" test "$("$M" explicit-default model/stl)" = com.orcaslicer.OrcaSlicer.desktop
  check "model/stl opens in OrcaSlicer" bash -c "gio mime model/stl | grep -q com.orcaslicer.OrcaSlicer.desktop"
  check "previous default recorded" grep -q '^model/stl=' "$MH/state/mime-before"
fi
"$M" doctor > "$T/doctor.log" 2>&1
check "doctor runs" grep -q 'red,' "$T/doctor.log"
check "doctor sees the window rules" grep -q 'window rules in' "$T/doctor.log"

echo "printers"
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
python3 "$ROOT/tests/mock-moonraker.py" --port "$PORT" --name Mock > "$T/mock.log" 2>&1 &
MOCK=$!
for _ in $(seq 1 50); do curl -fs "http://127.0.0.1:$PORT/printer/info" >/dev/null 2>&1 && break; sleep 0.1; done
"$M" printer add Mock "127.0.0.1:$PORT/" > "$T/printer-add.log" 2>&1
check "printer added with a normalized URL" test "$(jq -r '.printers[0].url' "$XDG_CONFIG_HOME/omarchy-maker/printers.json")" = "http://127.0.0.1:$PORT"
check "printers.json is owner-only" test "$(stat -c %a "$XDG_CONFIG_HOME/omarchy-maker/printers.json")" = 600
check "add says Moonraker answers" grep -q 'Moonraker answers' "$T/printer-add.log"
check "widget copied without symlinks" bash -c "test -f '$XDG_CONFIG_HOME/omarchy/plugins/layermaker.printers/manifest.json' && ! find '$XDG_CONFIG_HOME/omarchy/plugins/layermaker.printers' -type l | grep -q ."
check "printer test reports idle" bash -c "'$M' printer test Mock | grep -qx 'State: standby'"
curl -fs -X POST "http://127.0.0.1:$PORT/mock/start?file=parts/cube.gcode&seconds=100" >/dev/null
check "printer test reports the print" bash -c "'$M' printer test Mock | grep -qx 'File: parts/cube.gcode'"
check "re-adding a name replaces it" bash -c "'$M' printer add Mock 'http://127.0.0.1:$PORT' >/dev/null 2>&1; test \$(jq '.printers | length' '$XDG_CONFIG_HOME/omarchy-maker/printers.json') = 1"
check "bad URL refused" bash -c "! '$M' printer add Bad 'http://u:p@host:7125' 2>/dev/null"
kill "$MOCK" 2>/dev/null

echo "uninstall"
"$ROOT/uninstall.sh" > "$T/uninstall.log" 2>&1
check "hyprland.lua back to the original" cmp -s "$T/hyprland.orig" "$HOME/.config/hypr/hyprland.lua"
check "menu file back to the original" cmp -s "$T/menu.orig" "$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
check "window rules removed" test ! -e "$HOME/.config/hypr/maker.lua"
check "launcher removed" test ! -e "$XDG_DATA_HOME/applications/com.orcaslicer.OrcaSlicer.desktop"
check "commands removed" bash -c "test ! -e '$HOME/.local/bin/maker' && test ! -e '$HOME/.local/bin/maker-orca' && test ! -e '$HOME/.local/bin/maker-meshy'"
check "program and apps removed" test ! -e "$MH"
check "Printers widget removed" test ! -e "$XDG_CONFIG_HOME/omarchy/plugins/layermaker.printers"
check "printer list kept without --purge" test -f "$XDG_CONFIG_HOME/omarchy-maker/printers.json"
check "Orca setups kept without --purge" test -f "$XDG_CONFIG_HOME/omarchy-maker/orca-setups.json"
check "Orca layout memory removed" test ! -e "$HOME/.cache/omarchy-maker/orca-layout.json"
if command -v gio >/dev/null; then
  check "model/stl default removed" bash -c "! grep -q 'com.orcaslicer.OrcaSlicer.desktop' '$HOME/.config/mimeapps.list' 2>/dev/null"
fi

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
