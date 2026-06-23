# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CFB Data Tool (one-folder Windows build).
#   pyinstaller --noconfirm --clean packaging/cfbdatatool.spec
# Output: dist/CFBDataTool/CFBDataTool.exe
import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = os.path.dirname(SPECPATH)  # repo root (SPECPATH = packaging/)

datas, binaries, hiddenimports = [], [], []

# RapidOCR (bundles its ONNX models + config.yaml) and onnxruntime.
for pkg in ("rapidocr_onnxruntime", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# App data: ROI presets (JSON), star template (PNG), any stylesheets.
datas += collect_data_files("app", includes=["**/*.json", "**/*.png", "**/*.qss"])

# Ensure every app submodule is bundled — incl. the profile that self-registers.
hiddenimports += collect_submodules("app")

a = Analysis(
    [os.path.join(SPECPATH, "launch.py")],
    pathex=[ROOT],  # so `import app` resolves during analysis
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "tkinter", "matplotlib", "scipy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)

# Console window only when CFB_BUILD_CONSOLE=1 (handy for debugging a build).
console = os.environ.get("CFB_BUILD_CONSOLE") == "1"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CFBDataTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=console,
    icon=os.path.join(SPECPATH, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CFBDataTool",
)
