; Inno Setup script for CFB Data Tool.
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
; (run from the repo root, after PyInstaller has produced dist\CFBDataTool\)
; Produces: dist\installer\CFBDataTool-Setup.exe

#define MyAppName "CFB Data Tool"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Tyler Patchoski"
#define MyAppExeName "CFBDataTool.exe"

[Setup]
AppId={{B6A8F3C2-1D4E-4C9A-9E2B-CFB26DATATOOL}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\CFB Data Tool
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CFBDataTool-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; No admin rights needed — installs into the user's profile.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; The whole PyInstaller one-folder build.
Source: "..\dist\CFBDataTool\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
