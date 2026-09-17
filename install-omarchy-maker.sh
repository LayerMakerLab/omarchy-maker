#!/bin/bash
# install-omarchy-maker.sh: omarchy-maker onto this Omarchy machine in one go, from the latest release.
#
#   curl -fsSL https://github.com/LayerMakerLab/omarchy-maker/releases/latest/download/install-omarchy-maker.sh | bash
#   curl -fsSL ... | bash -s -- --apps orca,bambu,openscad    # say which apps to download up front
#   OMARCHY_MAKER_VERSION=v0.2.1 curl -fsSL ... | bash        # a particular release
#
# It downloads the release archive from GitHub, checks it against the SHA-256 sum published with it,
# unpacks it into ~/.local/share/omarchy-maker/checkout and runs install.sh there, which asks what to
# install. Run the same line again to update. Nothing needs sudo. To work from a git clone instead,
# see the README.
set -euo pipefail
tmp=""

main() {
  local repo=${OMARCHY_MAKER_REPO:-LayerMakerLab/omarchy-maker}
  local version=${OMARCHY_MAKER_VERSION:-latest}
  local checkout=${OMARCHY_MAKER_CHECKOUT:-${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-maker/checkout}
  local base got
  for tool in curl tar; do
    command -v "$tool" >/dev/null || { echo "install-omarchy-maker: $tool is missing (sudo pacman -S $tool)" >&2; exit 1; }
  done
  command -v sha256sum >/dev/null || command -v shasum >/dev/null || { echo "install-omarchy-maker: sha256sum is missing" >&2; exit 1; }
  if [ "$version" = latest ]; then base="https://github.com/$repo/releases/latest/download"
  else base="https://github.com/$repo/releases/download/$version"; fi
  base=${OMARCHY_MAKER_URL:-$base}

  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT           # tmp is deliberately not local: the trap runs after main returns
  echo "omarchy-maker: downloading $base/omarchy-maker.tar.gz"
  curl -fsSL --retry 3 -o "$tmp/omarchy-maker.tar.gz" "$base/omarchy-maker.tar.gz"
  curl -fsSL --retry 3 -o "$tmp/SHA256SUMS" "$base/SHA256SUMS"
  if command -v sha256sum >/dev/null; then got=$(sha256sum "$tmp/omarchy-maker.tar.gz" | cut -d' ' -f1)
  else got=$(shasum -a 256 "$tmp/omarchy-maker.tar.gz" | cut -d' ' -f1); fi
  if ! grep -q "^$got  omarchy-maker.tar.gz$" "$tmp/SHA256SUMS"; then
    echo "install-omarchy-maker: the download does not match the checksum published with the release; not installing" >&2
    exit 1
  fi
  mkdir -p "$tmp/tree"
  tar -xzf "$tmp/omarchy-maker.tar.gz" -C "$tmp/tree" --strip-components=1
  [ -x "$tmp/tree/install.sh" ] || { echo "install-omarchy-maker: the archive has no install.sh" >&2; exit 1; }
  version=$(tr -d '[:space:]' < "$tmp/tree/VERSION")

  if [ -d "$checkout/.git" ]; then
    echo "install-omarchy-maker: $checkout is a git clone; update it with git pull and ./install.sh there" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$checkout")"
  rm -rf "$checkout.new"
  mv "$tmp/tree" "$checkout.new"
  rm -rf "$checkout"
  mv "$checkout.new" "$checkout"
  echo "omarchy-maker $version is in $checkout; running its installer"
  cd "$checkout"
  rm -rf "$tmp"
  trap - EXIT
  # Piped through bash, stdin is this script; give the installer the terminal, when there is one, so it
  # can ask its questions. Over ssh without a terminal, or in a script, it takes what --apps says.
  if [ ! -t 0 ] && { : < /dev/tty; } 2>/dev/null; then
    exec ./install.sh "$@" < /dev/tty
  fi
  exec ./install.sh "$@"
}

main "$@"
