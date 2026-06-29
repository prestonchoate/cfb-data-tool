# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CFB Data Tool (cross-platform).
#   pyinstaller --noconfirm --clean packaging/cfbdatatool.spec
# Output:
#   Windows: dist/CFBDataTool/CFBDataTool.exe  (one-folder)
#   macOS:   dist/CFBDataTool.app              (.app bundle)
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = os.path.dirname(SPECPATH)  # repo root (SPECPATH = packaging/)
IS_MAC = sys.platform == "darwin"

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
    excludes=[
        "torch", "tkinter", "matplotlib", "scipy", "pandas",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQmlMeta",
        "PySide6.QtQmlModels", "PySide6.QtQmlWorkerScript",
        "PySide6.QtPdf", "PySide6.QtNetwork", "PySide6.QtDBus",
        "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtVirtualKeyboard",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

# Console window only when CFB_BUILD_CONSOLE=1 (handy for debugging a build).
console = os.environ.get("CFB_BUILD_CONSOLE") == "1"

if IS_MAC:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="CFBDataTool",
        debug=False,
        strip=True,
        upx=False,
        console=console,
    )
    app = BUNDLE(
        exe,
        a.binaries,
        a.datas,
        name="CFBDataTool.app",
        icon=os.path.join(SPECPATH, "icon.icns"),
        bundle_identifier="com.cfbdatatool.app",
        info_plist={
            "CFBundleShortVersionString": "0.1.3",
            "CFBundleName": "CFB Data Tool",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
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
