# Build CFB Data Tool: PyInstaller app bundle, then the Inno Setup installer.
# Usage (from repo root, with the venv created):  powershell -File packaging\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$py = ".\.venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $py)) {
    Write-Host "PyInstaller not found in .venv. Run: .\.venv\Scripts\pip install pyinstaller"
    exit 1
}

Write-Host "==> Building app bundle with PyInstaller..."
& $py --noconfirm --clean packaging\cfbdatatool.spec
Write-Host "==> Bundle ready: dist\CFBDataTool\CFBDataTool.exe"

$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    Write-Host "==> Building installer with Inno Setup..."
    & $iscc packaging\installer.iss
    Write-Host "==> Installer ready: dist\installer\CFBDataTool-Setup.exe"
} else {
    Write-Host ""
    Write-Host "Inno Setup not found. Install it from https://jrsoftware.org/isdl.php, then re-run this script."
}
