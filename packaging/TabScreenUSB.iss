; TabScreen USB kurulum sihirbazi (Inno Setup 6). Derleme: python build_installer.py (surum /DAppVersion ile gelir)
#ifndef AppVersion
  #error AppVersion tanimli degil: python build_installer.py ile derle
#endif

[Setup]
; AppId SABIT: degisirse sonraki surum ustune yazmaz, ikinci kurulum olur
AppId={{C2E7A1B4-6F3D-4A9B-8E15-3D0F7B92A6C4}
AppName=TabScreen USB
AppVersion={#AppVersion}
AppVerName=TabScreen USB {#AppVersion}
AppPublisher=Yusuf
AppPublisherURL=https://github.com/Yusufygc/Tableti_Yan_Ekran_Kullanmak
DefaultDirName={autopf}\TabScreenUSB
DefaultGroupName=TabScreen USB
; UAC sormaz: guncelleme sessiz calisir, derleme sonrasi deneme mumkun olur
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Guncellemede calisan uygulama kapatilir (dosya kilidi olmasin); yeniden acmayi [Run] yapar
CloseApplications=yes
RestartApplications=no
SetupIconFile=icons\app.ico
UninstallDisplayIcon={app}\TabScreenUSB.exe
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
; Surumlu ad: guncelleyici bu desene bakar (TabScreenUSB-Setup-X.Y.Z.exe)
OutputBaseFilename=TabScreenUSB-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\TabScreenUSB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TabScreen USB"; Filename: "{app}\TabScreenUSB.exe"
Name: "{autodesktop}\TabScreen USB"; Filename: "{app}\TabScreenUSB.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TabScreenUSB.exe"; Description: "{cm:LaunchProgram,TabScreen USB}"; Flags: nowait postinstall skipifsilent
; Uygulama ici guncelleme (/SILENT): kurulumdan sonra uygulama kendiliginden yeniden acilir
Filename: "{app}\TabScreenUSB.exe"; Flags: nowait; Check: RelaunchAfterUpdate

[Code]
function HasParam(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

{ /SILENT (guncelleme) yeniden acar; /VERYSILENT (derleme sonrasi deneme) acmaz. WizardVerySilent diye bir islev yoktur. }
function RelaunchAfterUpdate: Boolean;
begin
  Result := WizardSilent and not HasParam('/VERYSILENT');
end;
