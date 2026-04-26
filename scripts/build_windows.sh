#!/bin/bash

set -euo pipefail

if [[ "${OSTYPE:-}" == darwin* ]]; then
    echo "This build script is intended for Windows. Use scripts/build_macos.sh for macOS." >&2
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
SPEC_FILE="$ROOT_DIR/media_tools.spec"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/build/pyinstaller-cache}"

cd "$ROOT_DIR"

# Clean previous builds
rm -rf "$DIST_DIR" "$ROOT_DIR/build"

PYINSTALLER_CONFIG_DIR="$PYINSTALLER_CONFIG_DIR" \
    python -m PyInstaller --clean --noconfirm "$SPEC_FILE"

echo "Build complete! The results are available in: $DIST_DIR"
echo "Executable: $DIST_DIR/media-tools.exe (or media-tools folder)"
echo "You can create a ZIP archive for distribution."