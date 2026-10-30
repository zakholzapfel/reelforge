; Inno Setup 6. Build host only; users receive the generated Setup.exe.
#ifndef AppVersion
  #error AppVersion must be provided by the build script
#endif
[Setup]
AppId={{982F78B0-4570-4D05-A274-A71906A9A86E}
AppName=ReelForge
AppVersion={#AppVersion}
AppPublisher=Zakery Holzapfel
DefaultDirName={localappdata}\Programs\ReelForge
DefaultGroupName=ReelForge
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\desktop-dist
OutputBaseFilename=ReelForge-{#AppVersion}-Windows-Setup
SetupIconFile=..\reelforge\static\ReelForge.ico
UninstallDisplayIcon={app}\ReelForge.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\desktop-dist\ReelForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build\webview2\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\ReelForge"; Filename: "{app}\ReelForge.exe"
Name: "{autodesktop}\ReelForge"; Filename: "{app}\ReelForge.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Checking Microsoft WebView2 (internet may be required)..."; Flags: waituntilterminated
Filename: "{app}\ReelForge.exe"; Description: "Open ReelForge"; Flags: nowait postinstall skipifsilent
