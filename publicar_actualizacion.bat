@echo off
setlocal
REM ==== Publica una actualizacion en GitHub / Publishes an update to GitHub ====
REM  [1] Rapida (lo normal): sube solo el codigo; las PC instaladas bajan unicamente los archivos que cambiaron.
REM  [2] Completa: arma y publica el instalador (primera vez, o si cambia Python o una libreria).
REM Antes de publicar: suba el numero en taxapp\__init__.py y escriba las novedades en instalador\NOTAS_VERSION.md
cd /d "%~dp0"

for /f "tokens=2 delims==" %%v in ('findstr /b /c:"__version__" taxapp\__init__.py') do set "VER=%%v"
set "VER=%VER: =%"
set "VER=%VER:"=%"
for /f "usebackq delims=" %%r in (`powershell -NoProfile -Command "(Get-Content -Raw 'data\actualizaciones.json' | ConvertFrom-Json).repo"`) do set "REPO=%%r"
if not defined REPO set "REPO=netbiosop/DeclaraFacilUSA"

echo ================================================================
echo  Publicar DeclaraFacil USA %VER%  en  github.com/%REPO%
echo ================================================================

REM ---- Python (para el manifiesto)
call :findpy
if not defined PY (
    echo Python no encontrado. Ejecute primero crear_exe_windows.bat o instale Python. / Python not found.
    pause
    exit /b 1
)

REM ---- GitHub CLI
call :findgh
if not defined GH (
    echo Instalando GitHub CLI con winget... / Installing GitHub CLI...
    winget install -e --id GitHub.cli --accept-package-agreements --accept-source-agreements
    call :findgh
)
if not defined GH (
    echo Instale GitHub CLI desde / Install from: https://cli.github.com
    pause
    exit /b 1
)
%GH% auth status >nul 2>nul
if errorlevel 1 (
    echo Primera vez: inicie sesion en GitHub en el navegador. / First time: sign in to GitHub in the browser.
    %GH% auth login --hostname github.com --git-protocol https --web
    if errorlevel 1 goto fail
)

REM ---- Git
call :findgit
if not defined GIT (
    echo Instalando Git con winget... / Installing Git...
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
    call :findgit
)
if not defined GIT (
    echo Instale Git desde / Install from: https://git-scm.com/download/win
    pause
    exit /b 1
)
%GH% auth setup-git >nul 2>nul

REM ---- tipo de publicacion: si la base (__base__) todavia no tiene instalador publicado, va completa
for /f "tokens=2 delims==" %%b in ('findstr /b /c:"__base__" taxapp\__init__.py') do set "BASEV=%%b"
set "BASEV=%BASEV: =%"
set "BASEV=%BASEV:"=%"
if not defined BASEV set "BASEV=%VER%"
set "MODE=1"
%GH% release view v%BASEV% --repo %REPO% >nul 2>nul
if errorlevel 1 set "MODE=2"
if "%MODE%"=="2" (
    echo.
    echo El programa base %BASEV% todavia no tiene instalador publicado: se publicara el instalador completo.
    echo Base %BASEV% has no published installer yet: the full installer will be published.
    goto mode_ok
)
echo.
echo   [1] Rapida: solo los archivos modificados (recomendado) / Quick: changed files only
echo   [2] Completa: instalador nuevo (si cambio Python o una libreria) / Full installer
set "ANS="
set /p ANS=Elija / Choose [1/2] (Enter = 1): 
if "%ANS%"=="2" set "MODE=2"
:mode_ok

if "%MODE%"=="2" goto full
REM ---- [1] la version no debe estar publicada
%PY% herramientas\generar_manifiesto.py --check-new
if errorlevel 1 goto fail
goto code

:full
REM ---- [2] instalador completo: esta version pasa a ser la base
%PY% herramientas\fijar_base.py
if errorlevel 1 goto fail
%GH% release view v%VER% --repo %REPO% >nul 2>nul
if not errorlevel 1 (
    echo La version v%VER% ya tiene instalador publicado. Suba el numero en taxapp\__init__.py.
    goto fail
)
call crear_instalador_windows.bat nopause
if errorlevel 1 goto fail
set "FILE=instalador_salida\Instalar_DeclaraFacilUSA_%VER%.exe"
if not exist "%FILE%" goto fail
for /f "usebackq delims=" %%h in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%FILE%').Hash.ToLower()"`) do set "HASH=%%h"
> "%FILE%.sha256" echo %HASH%  Instalar_DeclaraFacilUSA_%VER%.exe
if not exist "instalador\NOTAS_VERSION.md" (> "instalador\NOTAS_VERSION.md" echo Version %VER%)
echo Subiendo el instalador / Uploading the installer...
%GH% release create v%VER% "%FILE%" "%FILE%.sha256" --repo %REPO% --title "DeclaraFacil USA %VER%" --notes-file "instalador\NOTAS_VERSION.md" --latest
if errorlevel 1 goto fail

:code
REM ---- manifiesto y codigo
%PY% herramientas\generar_manifiesto.py
if errorlevel 1 goto fail
if exist ".git" goto git_ready
echo Preparando Git por primera vez / Setting up Git for the first time...
%GIT% init -b main --separate-git-dir "%LOCALAPPDATA%\DeclaraFacilUSA_git" .
if errorlevel 1 goto fail
%GIT% remote add origin https://github.com/%REPO%.git
%GIT% fetch origin
%GIT% reset origin/main >nul 2>nul
:git_ready
%GIT% config core.autocrlf false
%GH% api user --jq .login > "%TEMP%\dfusa_user.txt" 2>nul
set "GHUSER="
set /p GHUSER=<"%TEMP%\dfusa_user.txt"
if not defined GHUSER set "GHUSER=DeclaraFacil"
%GIT% config user.name "%GHUSER%"
%GIT% config user.email "%GHUSER%@users.noreply.github.com"
%GIT% pull --rebase=false --no-edit origin main >nul 2>nul
%GIT% add -A
%GIT% diff --cached --quiet
if errorlevel 1 %GIT% commit -m "DeclaraFacil USA %VER%"
%GIT% push -u origin main
if errorlevel 1 goto fail

echo.
echo ================================================================
echo  Listo: version %VER% publicada / published.
echo  https://github.com/%REPO%
echo  Las PC instaladas la ofreceran al iniciar sesion un administrador.
echo ================================================================
pause
exit /b 0

:fail
echo.
echo ERROR: no se pudo publicar / publishing failed. Revise los mensajes de arriba.
pause
exit /b 1

:findpy
set "PY="
where py >nul 2>nul && (set "PY=py -3" & goto :eof)
if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (set PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3 & goto :eof)
if exist "%WINDIR%\py.exe" (set PY="%WINDIR%\py.exe" -3 & goto :eof)
where python >nul 2>nul && set "PY=python"
goto :eof

:findgh
set "GH="
where gh >nul 2>nul && (set "GH=gh" & goto :eof)
if exist "%ProgramFiles%\GitHub CLI\gh.exe" (set GH="%ProgramFiles%\GitHub CLI\gh.exe" & goto :eof)
if exist "%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe" set GH="%LOCALAPPDATA%\Programs\GitHub CLI\gh.exe"
goto :eof

:findgit
set "GIT="
where git >nul 2>nul && (set "GIT=git" & goto :eof)
if exist "%ProgramFiles%\Git\cmd\git.exe" (set GIT="%ProgramFiles%\Git\cmd\git.exe" & goto :eof)
if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set GIT="%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
goto :eof
