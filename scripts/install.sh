#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/808sgn-stem-lab"
VENV="$APP_DIR/.venv"

command -v ffmpeg >/dev/null 2>&1 || {
  echo "FFmpeg is required. On Ubuntu/Mint: sudo apt install ffmpeg" >&2
  exit 1
}

if ! command -v uv >/dev/null 2>&1; then
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required to install uv. On Ubuntu/Mint: sudo apt install curl" >&2
    exit 1
  }
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

mkdir -p "$APP_DIR"
uv venv --python 3.12 "$VENV"
uv pip install --python "$VENV/bin/python" "audio-separator[cpu]==0.47.0" audioread

echo
echo "Installed in: $VENV"
echo "Run scripts/stem-separate --help"
