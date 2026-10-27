@echo off
setlocal
REM ==== Crea / Builds DeclaraFacilUSA.exe con / with PyInstaller en / in %LOCALAPPDATA%\DeclaraFacilUSA_build\dist ====
REM Se ejecuta en la PC donde se CREA el programa (necesita Python). La PC donde se USA no necesita Python.
REM Runs on the PC that BUILDS the program (needs Python). The PC that USES it does not need Python.
cd /d "%~dp0"
REM La compilacion se hace FUERA de OneDrive (OneDrive bloquea los archivos temporales: "Access is denied").
REM The build runs OUTSIDE OneDrive (OneDrive locks the temporary files).
set "SRC=%~dp0"
set "BUILD=%LOCALAPPDATA%\DeclaraFacilUSA_build"
set "OUT=%BUILD%\dist"

call :findpy
if not defined PY (
    echo Python no encontrado. Intentando instalarlo con winget... / Python not found. Trying winget...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    call :findpy
)
if not defined PY (
    echo.
    echo Instale Python desde / Install Python from: https://www.python.org/downloads/
    echo Marque / Check "Add python.exe to PATH" y vuelva a ejecutar este archivo / and run this file again.
    if /i not "%~1"=="nopause" pause
    exit /b 1
)
echo Usando / Using: %PY%

echo.
echo Instalando herramientas / Installing tools (PyInstaller, reportlab, pypdf)...
%PY% -m pip install --user --upgrade pyinstaller reportlab pypdf
if errorlevel 1 goto fail

echo.
echo Creando el ejecutable / Building the executable (1-3 min)...
REM restos de compilaciones anteriores dentro de OneDrive (si no se pueden borrar, no importa)
if exist "%SRC%build" rmdir /s /q "%SRC%build" >nul 2>nul
if exist "%SRC%dist" rmdir /s /q "%SRC%dist" >nul 2>nul
if exist "%SRC%DeclaraFacilUSA.spec" del /q "%SRC%DeclaraFacilUSA.spec" >nul 2>nul
if exist "%BUILD%\work" rmdir /s /q "%BUILD%\work" >nul 2>nul
if exist "%OUT%\DeclaraFacilUSA" rmdir /s /q "%OUT%\DeclaraFacilUSA" >nul 2>nul
if not exist "%BUILD%" mkdir "%BUILD%"
for /d /r "%SRC%taxapp" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d" >nul 2>nul

%PY% -m PyInstaller --noconfirm --clean --windowed --name DeclaraFacilUSA ^
  --distpath "%OUT%" --workpath "%BUILD%\work" --specpath "%BUILD%" ^
  --icon "%SRC%assets\DeclaraFacilUSA.ico" ^
  --add-data "%SRC%data;data" --add-data "%SRC%docs;docs" --add-data "%SRC%assets;assets" ^
  --add-data "%SRC%taxapp;taxapp" ^
  --paths "%SRC%." --collect-submodules taxapp --collect-submodules pypdf ^
  --collect-submodules tkinter --collect-submodules json --collect-submodules email --collect-submodules xml ^
  --collect-submodules urllib --collect-submodules http --collect-submodules importlib ^
  --hidden-import csv --hidden-import decimal --hidden-import fractions --hidden-import statistics ^
  --hidden-import sqlite3 --hidden-import uuid --hidden-import calendar --hidden-import difflib ^
  --hidden-import textwrap --hidden-import secrets --hidden-import gzip --hidden-import html ^
  --hidden-import reportlab.graphics.barcode.common ^
  "%SRC%main.py"
if errorlevel 1 goto fail
if not exist "%OUT%\DeclaraFacilUSA\DeclaraFacilUSA.exe" goto fail

echo.
echo Listo / Done: %OUT%\DeclaraFacilUSA\DeclaraFacilUSA.exe
echo Para otra PC use crear_instalador_windows.bat, o copie esa carpeta COMPLETA (incluye _internal).
echo For another PC use crear_instalador_windows.bat, or copy that WHOLE folder (includes _internal).
if /i "%~1"=="nopause" exit /b 0
start "" explorer "%OUT%\DeclaraFacilUSA"
pause
exit /b 0

:fail
echo.
echo ERROR: no se pudo crear el ejecutable / the build failed. Revise los mensajes de arriba / see messages above.
if /i not "%~1"=="nopause" pause
exit /b 1

:findpy
set "PY="
where py >nul 2>nul && (set "PY=py -3" & goto :eof)
if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (set PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3 & goto :eof)
if exist "%WINDIR%\py.exe" (set PY="%WINDIR%\py.exe" -3 & goto :eof)
where python >nul 2>nul && set "PY=python"
goto :eof
