# KingIn Installer Script (Inno Setup)
# Save this as install_kingin.iss

[Setup]
AppName=KingIn Trading System
AppVersion=2.0
DefaultDirName={pf}\KingIn
DefaultGroupName=KingIn
UninstallDisplayIcon={app}\KingIn_v2.exe
OutputBaseFilename=KingIn_Installer
Compression=lzma
SolidCompression=yes
SetupIconFile=frontend\its_icon.ico

[Files]
Source: "dist\KingIn_v2.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "license.kingin"; DestDir: "{app}"; Flags: ignoreversion
; Include any additional resources if needed, e.g., configuration files

[Icons]
Name: "{group}\KingIn"; Filename: "{app}\KingIn_v2.exe"
Name: "{commondesktop}\KingIn"; Filename: "{app}\KingIn_v2.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\KingIn_v2.exe"; Description: "Launch KingIn"; Flags: nowait postinstall skipifsilent
