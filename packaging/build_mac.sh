#!/usr/bin/env bash
# Build CFB Data Tool on macOS: PyInstaller .app bundle, then optional DMG.
# Usage (from repo root, with the venv activated):  bash packaging/build_mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/pyinstaller"
if [ ! -f "$PY" ]; then
    echo "PyInstaller not found in .venv. Run: pip install pyinstaller"
    exit 1
fi

echo "==> Building .app bundle with PyInstaller..."
"$PY" --noconfirm --clean packaging/cfbdatatool.spec
echo "==> Bundle ready: dist/CFBDataTool.app"

# Create a DMG if create-dmg is installed (brew install create-dmg).
if command -v create-dmg &>/dev/null; then
    echo "==> Building DMG installer..."
    mkdir -p dist/installer
    create-dmg \
        --volname "CFB Data Tool" \
        --volicon "packaging/icon.icns" \
        --window-size 600 400 \
        --icon "CFBDataTool.app" 150 200 \
        --app-drop-link 450 200 \
        "dist/installer/CFBDataTool.dmg" \
        "dist/CFBDataTool.app"
    echo "==> DMG ready: dist/installer/CFBDataTool.dmg"
else
    echo ""
    echo "create-dmg not found. Install it for a DMG installer:"
    echo "  brew install create-dmg"
    echo "The .app bundle at dist/CFBDataTool.app is ready to distribute as-is."
fi
