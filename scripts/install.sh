#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab"
VENV="$APP_DIR/.venv"
VENV_MARKER="$VENV/.stemlab-managed"
APP_CODE="$APP_DIR/app"
MARKER="$APP_CODE/.stemlab-managed"

command -v ffmpeg >/dev/null 2>&1 || {
  echo "FFmpeg is required (ffmpeg and ffprobe must be on PATH)." >&2
  exit 1
}
command -v ffprobe >/dev/null 2>&1 || {
  echo "ffprobe is required (provided by FFmpeg)." >&2
  exit 1
}

command -v uv >/dev/null 2>&1 || {
  echo "uv is required on PATH; install it before running this installer." >&2
  exit 1
}

if [[ -L "$APP_DIR" || -L "$APP_CODE" || -L "$MARKER" || -L "$VENV" ||
      ( -e "$APP_CODE" && ! -f "$MARKER" ) ]]; then
  echo "Refusing to replace an unowned or symlinked app directory: $APP_CODE" >&2
  exit 1
fi
if [[ -e "$APP_CODE" ]] && ! grep -Fxq '808sgn-stem-lab-app-v1' "$MARKER"; then
  echo "Refusing to replace an unowned app directory: $APP_CODE" >&2
  exit 1
fi
if [[ -e "$VENV" || -L "$VENV" ]]; then
  if [[ ! -d "$VENV" || -L "$VENV_MARKER" || ! -f "$VENV_MARKER" ]] ||
     ! grep -Fxq '808sgn-stem-lab-venv-v1' "$VENV_MARKER" ||
     [[ ! -f "$VENV/pyvenv.cfg" || ! -x "$VENV/bin/python" ]]; then
    echo "Refusing to modify an unowned or invalid Python environment: $VENV" >&2
    exit 1
  fi
fi
for target in "$APP_CODE/gui" "$APP_CODE/scripts" \
              "$APP_CODE/gui/producer_qt.py" "$APP_CODE/scripts/stem-separate" \
              "$APP_CODE/scripts/stemlab-gui" "$APP_CODE/scripts/install-desktop.sh" \
              "$APP_CODE/LICENSE-CODE"; do
  if [[ -L "$target" ]]; then
    echo "Refusing to replace a symlink: $target" >&2
    exit 1
  fi
done

mkdir -p "$APP_DIR"
# Never inherit uv's environment switch that can clear a target venv.
unset UV_VENV_CLEAR UV_VENV_FORCE
if [[ ! -e "$VENV" ]]; then
  uv venv --no-python-downloads --python 3.12 "$VENV"
  printf '%s\n' '808sgn-stem-lab-venv-v1' > "$VENV_MARKER"
fi
uv pip install --python "$VENV/bin/python" "audio-separator[cpu]==0.47.0" "audioread==3.0.1" "PySide6==6.11.2"

mkdir -p "$APP_CODE/gui" "$APP_CODE/scripts"
printf '%s\n' '808sgn-stem-lab-app-v1' > "$MARKER"
install -m 644 "$ROOT/gui/producer_qt.py" "$APP_CODE/gui/producer_qt.py"
install -m 755 "$ROOT/scripts/stem-separate" "$APP_CODE/scripts/stem-separate"
install -m 755 "$ROOT/scripts/stemlab-gui" "$APP_CODE/scripts/stemlab-gui"
install -m 755 "$ROOT/scripts/install-desktop.sh" "$APP_CODE/scripts/install-desktop.sh"
install -m 644 "$ROOT/LICENSE-CODE" "$APP_CODE/LICENSE-CODE"

echo
echo "Installed in: $APP_DIR"
echo "Run: $APP_CODE/scripts/stemlab-gui"
echo "Optional application menu: bash scripts/install-desktop.sh"
