; =====================================================================================================
;  DeclaraFacil USA - script del instalador / installer script (Inno Setup 6, https://jrsoftware.org)
;  No lo ejecute directamente: use crear_instalador_windows.bat (primero crea dist\DeclaraFacilUSA).
;  Do not run directly: use crear_instalador_windows.bat (it builds dist\DeclaraFacilUSA first).
; =====================================================================================================

#ifndef MyAppVersion
  #define MyAppVersion "1.3.0"
#endif
#ifndef BuildDir
  #define BuildDir "..\dist\DeclaraFacilUSA"
#endif
#define MyAppName "DeclaraFacil USA"
#define MyAppExe "DeclaraFacilUSA.exe"

[Setup]
; El AppId identifica la aplicacion: las versiones nuevas se instalan encima de las anteriores.
AppId={{8C3B5E2A-6F1D-4B7A-9E2C-3D5F7A1B9C40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=DeclaraFacil USA
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\DeclaraFacilUSA
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Sin permisos de administrador: se instala para el usuario actual (AppData\Local\Programs).
; En la primera pantalla se puede elegir instalar para todos los usuarios.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\instalador_salida
OutputBaseFilename=Instalar_DeclaraFacilUSA_{#MyAppVersion}
SetupIconFile=..\assets\DeclaraFacilUSA.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
ShowLanguageDialog=auto

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.DataNote=Sus declaraciones, usuarios y configuración se guardan en Documentos\DeclaraFacilUSA y no se borran al desinstalar ni al actualizar.
english.DataNote=Your returns, users and settings are stored in Documents\DeclaraFacilUSA and are not deleted when you uninstall or update.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; limpia los archivos internos de la version anterior antes de copiar los nuevos
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autoprograms}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; actualizacion automatica (instalacion silenciosa lanzada por la app): volver a abrirla al terminar
Filename: "{app}\{#MyAppExe}"; Flags: nowait; Check: WizardSilent

[Code]
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption := WizardForm.FinishedLabel.Caption + #13#10#13#10 + CustomMessage('DataNote');
end;
