#!/bin/zsh

set -euo pipefail

if [[ "${OSTYPE:-}" != darwin* ]]; then
    echo "This build script only works on macOS." >&2
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
SPEC_FILE="$ROOT_DIR/media_tools.spec"
APP_BUNDLE_NAME="Media Tools.app"
DMG_NAME="media-tools-macos.dmg"
DMG_VOLUME_NAME="Media Tools"
STAGING_DIR="$DIST_DIR/dmg-root-$$"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/build/pyinstaller-cache}"

if [[ -x "$ROOT_DIR/.venv/bin/python3" ]]; then
    PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python3}"
else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR"

PYINSTALLER_CONFIG_DIR="$PYINSTALLER_CONFIG_DIR" \
    "$PYTHON_BIN" -m PyInstaller --clean --noconfirm "$SPEC_FILE"

APP_PATH="$DIST_DIR/$APP_BUNDLE_NAME"
if [[ ! -d "$APP_PATH" ]]; then
    echo "Expected app bundle not found: $APP_PATH" >&2
    exit 1
fi

mkdir -p "$STAGING_DIR"
ditto "$APP_PATH" "$STAGING_DIR/$APP_BUNDLE_NAME"
ln -sfn /Applications "$STAGING_DIR/Applications"

DMG_PATH="$DIST_DIR/$DMG_NAME"
hdiutil create \
    -volname "$DMG_VOLUME_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo "Built app bundle: $APP_PATH"
echo "Built dmg archive: $DMG_PATH"
