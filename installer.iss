[Setup]
AppId={{8E9A4B2D-3F1C-4A8E-9B7D-2C5F8E1A4D6B}
AppName=Atlas
AppVersion=1.0.0
AppPublisher=Divyansh Kumar
DefaultDirName={autopf}\Atlas
DefaultGroupName=Atlas
AllowNoIcons=yes
OutputDir=D:\Atlas\installer_output
OutputBaseFilename=AtlasSetup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; Closes Atlas.exe automatically if it is running during an upgrade or uninstall
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Packages the entire PyInstaller One-Folder build (including _internal and models)
Source: "D:\Atlas\dist\Atlas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Atlas"; Filename: "{app}\Atlas.exe"
Name: "{group}\{cm:UninstallProgram,Atlas}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Atlas"; Filename: "{app}\Atlas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Atlas.exe"; Description: "{cm:LaunchProgram,Atlas}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Optional: clean up any leftover temp files in the install folder
Type: filesandordirs; Name: "{app}"

