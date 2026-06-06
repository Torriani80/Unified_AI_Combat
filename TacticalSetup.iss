; Unified AI Combat - Inno Setup Installer
; Requer Inno Setup 6.x

#define AppName "Unified AI Combat"
#define AppExeName "TacticalSetup.exe"
#define AppVersion "1.0.0"
#define AppPublisher "Unified AI Combat"
#define AppURL "https://github.com/"
#define OutputDir "dist\installer\"
#define OutputBaseFilename "Unified_AI_Combat_Setup_v{#define AppVersion}"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}
AppName={#define AppName}
AppVersion={#define AppVersion}
AppPublisher={#define AppPublisher}
AppPublisherURL={#ifdef AppURL}{#define AppURL}{#endif}
DefaultDirName={pf}\{#define AppName}
DefaultGroupName={#define AppName}
OutputDir={#define OutputDir}
OutputBaseFilename={#define OutputBaseFilename}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
LicenseFile=LICENSE.txt
DisableStartupPrompt=yes
DisableDirPage=no
DisableProgramGroupPage=no
DisableReadyPage=no
DisableFinishedPage=no
DisableWelcomePage=no
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#define AppName}"
Type: filesandordirs; Name: "{appdata}\{#define AppName}"

[Dirs]
Name: "{app}"
Name: "{app}\logs"
Name: "{app}\assets"
Name: "{app}\plugins"
Name: "{app}\templates"
Name: "{app}\config"
Name: "{app}\data"
Name: "{app}\presets"
Name: "{app}\sounds"
Name: "{app}\translations"
Name: "{appdata}\{#define AppName}"

[Files]
Source: "dist\Unified_Combat_V1\{#define AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Unified_Combat_V1\_internal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\Unified_Combat_V1\qt.conf"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "weapon_templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\{#define AppName}"; Filename: "{app}\{#define AppExeName}"
Name: "{group}\{cm:ProgramOnTheWeb,{#define AppURL}}"; Filename: "{#define AppURL}"
Name: "{group}\{cm:UninstallProgram,{#define AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#define AppName}"; Filename: "{app}\{#define AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#define AppExeName}"; Description: "{cm:LaunchProgram,{#define AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  MsgBox('IMPORTANTE: Coloque o arquivo serviceAccountKey.json em:' + #13#10 +
    '%APPDATA%\Unified_AI_Combat\' + #13#10 + #13#10 +
    'Sem esse arquivo o Firebase nao funcionara.', mbInformation, MB_OK);
end;
