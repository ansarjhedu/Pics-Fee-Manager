; PICS Fee Desk setup wizard.
; Principal build: ISCC installer\PICSFeeDesk.iss
; Clerk base:     ISCC /DClerkBuild=1 installer\PICSFeeDesk.iss
; The principal build embeds the clerk base. Compile the clerk base first.

#ifndef ClerkBuild
#define ClerkBuild "0"
#endif

#define AppName "PICS Fee Desk"
#define AppVersion "1.0.0"
#define AppPublisher "Punjab Inter College of Sciences"

[Setup]
AppId={{8F4E2C1A-6B7D-4E90-9A3C-1D5F0B8E7A42}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppPublisher}\Fee Desk
DefaultGroupName={#AppName}
DisableProgramGroupPage=no
#if ClerkBuild == "1"
OutputDir=..\dist\setup-stage
OutputBaseFilename=PICS Clerk Setup Base
#else
OutputDir=..\dist
OutputBaseFilename=PICS Fee Desk Setup
#endif
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
SetupIconFile=..\assets\pics-fee.ico
#if ClerkBuild == "1"
UninstallDisplayIcon={app}\PICS Fee Clerk.exe
#else
UninstallDisplayIcon={app}\PICS Fee Principal.exe
#endif
CloseApplications=yes
RestartApplications=no
SetupLogging=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[InstallDelete]
Type: filesandordirs; Name: "{app}\*"

[Files]
#if ClerkBuild == "1"
Source: "..\dist\setup-stage\clerk\PICS Fee Clerk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "..\dist\setup-stage\principal\PICS Fee Principal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\setup-stage\PICS Clerk Setup Base.exe"; DestDir: "{app}"; DestName: "clerk-setup.base.exe"; Flags: ignoreversion nocompression
Source: "clerk-setup.stub.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
#if ClerkBuild == "1"
Name: "{group}\{#AppName}"; Filename: "{app}\PICS Fee Clerk.exe"; IconFilename: "{app}\PICS Fee Clerk.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\PICS Fee Clerk.exe"; IconFilename: "{app}\PICS Fee Clerk.exe"
#else
Name: "{group}\{#AppName}"; Filename: "{app}\PICS Fee Principal.exe"; IconFilename: "{app}\PICS Fee Principal.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\PICS Fee Principal.exe"; IconFilename: "{app}\PICS Fee Principal.exe"
#endif
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
#if ClerkBuild == "1"
Filename: "{app}\PICS Fee Clerk.exe"; Description: "Open PICS Fee Desk"; Flags: postinstall nowait skipifsilent
#else
Filename: "{app}\PICS Fee Principal.exe"; Description: "Open PICS Fee Desk"; Flags: postinstall nowait skipifsilent
#endif

[Code]
var
  InfoPage: TOutputMsgMemoWizardPage;

function IsPrincipal: Boolean;
begin
#if ClerkBuild == "1"
  Result := False;
#else
  Result := True;
#endif
end;

function IsClerk: Boolean;
begin
  Result := not IsPrincipal;
end;

function ProgramDataRolePath: String;
begin
  Result := ExpandConstant('{commonappdata}\PICS\FeeDesk\machine.role');
end;

function ReadRoleFile(const Path: String): String;
var
  Text: AnsiString;
begin
  Result := '';
  if FileExists(Path) and LoadStringFromFile(Path, Text) then
    Result := LowerCase(Trim(String(Text)));
  if (Result <> 'principal') and (Result <> 'clerk') then
    Result := '';
end;

function LockedRole: String;
begin
  Result := ReadRoleFile(ProgramDataRolePath);
  if Result = '' then
    Result := ReadRoleFile(ExpandConstant('{app}\role.txt'));
  if (not FileExists(ExpandConstant('{commonappdata}\PICS\FeeDesk\fee.db'))) and
     FileExists(ExpandConstant('{userappdata}\PICS\FeeDesk\connection.json')) then
    Result := 'clerk';
  if (Result = '') and FileExists(ExpandConstant('{commonappdata}\PICS\FeeDesk\fee.db')) then
    Result := 'principal';
end;

procedure RememberRole(const Role: String);
begin
  ForceDirectories(ExpandConstant('{commonappdata}\PICS\FeeDesk'));
  SaveStringToFile(ProgramDataRolePath, Role, False);
end;

function MachineText: String;
begin
  if IsPrincipal then
    Result :=
      'This computer keeps the only copy of the fee records.' + #13#10 + #13#10 +
      'The program itself is installed in the folder you choose next. The records are stored separately, in:' + #13#10 +
      'C:\ProgramData\PICS\FeeDesk' + #13#10 + #13#10 +
      'fee.db holds the students, classes, vouchers, and approvals.' + #13#10 +
      'backups holds the copies made from the Backup page.' + #13#10 +
      'cert.pem is the identity placed inside each clerk''s setup file.' + #13#10 + #13#10 +
      'After installation, open PICS Fee Desk and create the principal account. Add each clerk on the Clerks page. That page saves a setup file for the clerk, with this computer''s address and fingerprint already inside. Copy that file to the clerk''s computer and run it.' + #13#10 + #13#10 +
      'A clerk computer does not store these records. It connects to this computer over the college network on port 8765. This installer allows that port through Windows Firewall on private and domain networks.' + #13#10 + #13#10 +
      'Leave this desk open while a clerk is working. Removing the program does not delete the records.'
  else
    Result :=
      'This computer connects to the principal''s desk. The address and fingerprint are already inside this setup file, so there is nothing to type.' + #13#10 + #13#10 +
      'It saves only that connection, for the Windows user who installs it:' + #13#10 +
      'AppData\Roaming\PICS\FeeDesk\connection.json' + #13#10 + #13#10 +
      'Every student, voucher, and approval stays on the principal''s computer, in:' + #13#10 +
      'C:\ProgramData\PICS\FeeDesk\fee.db' + #13#10 + #13#10 +
      'Leave the principal''s desk open. Both computers must be on the college network.' + #13#10 + #13#10 +
      'Removing the program from this computer does not delete the records. They were never stored here.'
end;

procedure InitializeWizard;
begin
  InfoPage := CreateOutputMsgMemoPage(wpWelcome,
    'Where the records live',
    'The program and the fee records are kept in different places.',
    '',
    '');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = InfoPage.ID then
    InfoPage.RichEditViewer.Lines.Text := MachineText;
  if CurPageID = wpFinished then
  begin
    if IsPrincipal then
      WizardForm.FinishedLabel.Caption :=
        'PICS Fee Desk is installed on the principal''s computer.' + #13#10 + #13#10 +
        'Open it and create the principal account. On the Clerks page, add each clerk and save that clerk''s setup file. Copy the file to their computer and run it. The address and fingerprint are already inside.' + #13#10 + #13#10 +
        'Records are kept in C:\ProgramData\PICS\FeeDesk. Leave this computer on while a clerk works.'
    else
      WizardForm.FinishedLabel.Caption :=
        'PICS Fee Desk is installed on this clerk computer.' + #13#10 + #13#10 +
        'The principal''s address and fingerprint are already saved. Open PICS Fee Desk and sign in with the username and password the principal created.' + #13#10 + #13#10 +
        'This computer does not keep the fee records. Leave the principal''s desk open while you work.';
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Locked: String;
begin
  Result := '';
  Locked := LockedRole;
  if Locked <> '' then
    RememberRole(Locked);
  if (Locked = 'clerk') and IsPrincipal then
    Result := 'This computer is a clerk desk. The setup cannot turn it into the principal''s computer, so it cannot open the fee records kept there.';
  if (Locked = 'principal') and IsClerk then
    Result := 'This computer keeps the fee records. The setup cannot turn it into a clerk desk.';
end;

procedure InstallBundledConnection;
var
  Host, Fingerprint, Clerk, PortText, Dest, Payload: String;
begin
  Host := Trim(ExpandConstant('{param:HOST|}'));
  Fingerprint := Trim(ExpandConstant('{param:FP|}'));
  Clerk := Trim(ExpandConstant('{param:CLERK|}'));
  PortText := Trim(ExpandConstant('{param:PORT|8765}'));
  if (Host = '') or (Fingerprint = '') or (PortText = '') then
    Exit;
  ForceDirectories(ExpandConstant('{userappdata}\PICS\FeeDesk'));
  Dest := ExpandConstant('{userappdata}\PICS\FeeDesk\connection.json');
  Payload := '{"host":"' + Host + '","port":' + PortText + ',"fingerprint":"' + Fingerprint + '"';
  if Clerk <> '' then
    Payload := Payload + ',"username":"' + Clerk + '"';
  Payload := Payload + '}';
  SaveStringToFile(Dest, Payload, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  RoleFile: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  RoleFile := ExpandConstant('{app}\role.txt');
  if IsPrincipal then
  begin
    SaveStringToFile(RoleFile, 'principal', False);
    RememberRole('principal');
    Exec('netsh', 'advfirewall firewall delete rule name="PICS Fee Desk"', '', SW_HIDE, ewWaitUntilTerminated, Code);
    Exec('netsh', 'advfirewall firewall add rule name="PICS Fee Desk" dir=in action=allow protocol=TCP localport=8765 profile=private,domain', '', SW_HIDE, ewWaitUntilTerminated, Code);
  end
  else
  begin
    SaveStringToFile(RoleFile, 'clerk', False);
    RememberRole('clerk');
    InstallBundledConnection;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Role: AnsiString;
  Code: Integer;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  if LoadStringFromFile(ExpandConstant('{app}\role.txt'), Role) then
    if Trim(String(Role)) = 'principal' then
      Exec('netsh', 'advfirewall firewall delete rule name="PICS Fee Desk"', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
