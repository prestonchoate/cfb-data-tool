#!/usr/bin/env bash
# Build CFB Data Tool on Linux: PyInstaller one-folder bundle, then AppImage.
# Usage (from repo root, with the venv activated):  bash packaging/build_linux.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/pyinstaller"
if [ ! -f "$PY" ]; then
    PY="$(command -v pyinstaller || true)"
fi
if [ -z "$PY" ]; then
    echo "PyInstaller not found. Run: pip install -e .[dev,linux]"
    exit 1
fi

echo "==> Building one-folder bundle with PyInstaller..."
"$PY" --noconfirm --clean packaging/cfbdatatool.spec
echo "==> Bundle ready: dist/CFBDataTool/"

APPDIR="dist/CFBDataTool.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a dist/CFBDataTool/. "$APPDIR/usr/bin/"
cp packaging/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/cfb-data-tool.desktop "$APPDIR/cfb-data-tool.desktop"
cp packaging/cfb-data-tool.desktop "$APPDIR/usr/share/applications/cfb-data-tool.desktop"
cp app/resources/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/cfb-data-tool.png"
ln -sf usr/share/icons/hicolor/256x256/apps/cfb-data-tool.png "$APPDIR/cfb-data-tool.png"

APPIMAGETOOL="packaging/tools/appimagetool-x86_64.AppImage"
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "==> Downloading appimagetool..."
    mkdir -p packaging/tools
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

ARCH="$(uname -m)"
OUTPUT="dist/CFBDataTool-${ARCH}.AppImage"
rm -f "$OUTPUT"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" -o "$OUTPUT"
echo "==> AppImage ready: $OUTPUT"

if [ "${CFB_SMOKE:-}" = "1" ]; then
    echo "==> Running smoke test..."
    QT_QPA_PLATFORM=offscreen CFB_SMOKE=1 "$OUTPUT"
    cat dist/CFBDataTool/smoke_result.txt
fi
