; Reclaimerr Inno Setup installer script
; Auto-run after the PyInstaller build step in CI.
; Pass the version on the command line:
;   ISCC.exe /DMyAppVersion="0.1.0" installer\reclaimerr.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName    "Reclaimerr"
#define MyAppExe     "reclaimerr.exe"
#define MyAppURL     "https://github.com/dionysuspark69-claw/Reclaimerr"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Install per-user to %LocalAppData%\Programs — no admin prompt needed.
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

; Output
OutputDir=..\installer-output
OutputBaseFilename=Reclaimerr-Setup
SetupIconFile=..\frontend\static\favicon.ico
UninstallDisplayIcon={app}\{#MyAppExe}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; UI
WizardStyle=modern
DisableWelcomePage=no
LicenseFile=
InfoBeforeFile=

; Version info embedded in the installer exe
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart";   Description: "Start {#MyAppName} &automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Entire PyInstaller onedir bundle
Source: "..\dist\reclaimerr\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Desktop (optional task)
Name: "{autodesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Auto-start on login (optional task — written to HKCU so no admin needed)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExe}"""; \
  Tasks: autostart; Flags: uninsdeletevalue

[Run]
; Offer to launch the app after installation finishes
Filename: "{app}\{#MyAppExe}"; \
  Description: "Launch {#MyAppName} now"; \
  Flags: nowait postinstall skipifsilent
