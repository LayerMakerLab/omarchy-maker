#!/bin/bash
# build-wlrctl.sh DEST — build wlrctl into DEST/wlrctl, with a `pointer wheel N` action added.
#
# maker-orca clicks OrcaSlicer's tabs and lists through wlrctl's virtual pointer, and scrolls those lists
# with mouse-wheel notches: they ignore the smooth touchpad scrolling stock `wlrctl pointer scroll` sends.
# Needs git, gcc, pkg-config, wayland-scanner, wayland and libxkbcommon (all on Omarchy with base-devel).
set -euo pipefail
DEST=${1:?usage: build-wlrctl.sh DEST}
REPO=https://git.sr.ht/~brocellous/wlrctl
COMMIT=c6bc60820bb8786c7509e651bcae9393a738f180     # tested 2026-09-15 with Hyprland 0.56.2
HERE=$(cd "$(dirname "$0")" && pwd)
for t in git gcc pkg-config wayland-scanner; do command -v "$t" >/dev/null || { echo "missing $t (sudo pacman -S --needed base-devel wayland)" >&2; exit 1; }; done
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
git clone -q "$REPO" "$WORK/wlrctl"
git -C "$WORK/wlrctl" checkout -q "$COMMIT"
python3 "$HERE/wlrctl-wheel.py" "$WORK/wlrctl"
mkdir -p "$WORK/wlrctl/build" "$DEST"
cd "$WORK/wlrctl/build"
for x in ../protocol/*.xml; do
  b=$(basename "$x" .xml)
  wayland-scanner client-header "$x" "$b-client-protocol.h"
  wayland-scanner private-code "$x" "$b-protocol.c"
done
gcc -O2 -std=gnu11 -Wno-incompatible-pointer-types -DWLRCTL_VERSION='"0.2.2+wheel"' -o "$DEST/wlrctl.new" -I. -I../include \
  ../*.c ./*-protocol.c $(pkg-config --cflags --libs wayland-client xkbcommon) -lm
mv "$DEST/wlrctl.new" "$DEST/wlrctl"
echo "built $DEST/wlrctl"
