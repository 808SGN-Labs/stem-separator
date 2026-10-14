#!/usr/bin/env bash
# Register the local StemLab source checkout in the Linux desktop app menu.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
LAUNCHER="$ROOT/scripts/stemlab-gui"
APPLICATIONS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP="$APPLICATIONS/808sgn-stemlab.desktop"

[[ -x "$LAUNCHER" ]] || { echo "Launcher missing or not executable: $LAUNCHER" >&2; exit 1; }

if [[ "${1:-}" == "--remove" ]]; then
  if [[ -L "$DESKTOP" ]]; then
    echo "Refusing to remove a symlinked desktop entry: $DESKTOP" >&2
    exit 1
  fi
  if [[ -f "$DESKTOP" ]] && grep -Fxq "# StemLab-Source: $ROOT" "$DESKTOP"; then
    rm -- "$DESKTOP"
    echo "Removed $DESKTOP"
  else
    echo "No matching StemLab desktop entry to remove."
  fi
  exit 0
fi
[[ $# -eq 0 ]] || { echo "Usage: bash scripts/install-desktop.sh [--remove]" >&2; exit 2; }

# Desktop Entry Exec uses double-quoted paths, escaping special characters.
desktop_quote() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//\$/\\$}
  value=${value//\`/\\\`}
  printf '"%s"' "$value"
}

mkdir -p -- "$APPLICATIONS"
if [[ -L "$DESKTOP" ]]; then
  echo "Refusing to overwrite a symlinked desktop entry: $DESKTOP" >&2
  exit 1
fi
if [[ -e "$DESKTOP" ]] && ! grep -Fxq "# StemLab-Source: $ROOT" "$DESKTOP"; then
  echo "Refusing to overwrite another desktop entry: $DESKTOP" >&2
  exit 1
fi

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=808SGN StemLab
GenericName=Audio Stem Separator
Comment=Local offline audio stem separation
Exec=$(desktop_quote "$LAUNCHER")
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=true
# StemLab-Source: $ROOT
EOF
echo "Installed desktop entry: $DESKTOP"
