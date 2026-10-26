@echo off
setlocal
REM ==== Crea el instalador / Builds the installer: instalador_salida\Instalar_DeclaraFacilUSA_<version>.exe ====
REM 1) crea el ejecutable con PyInstaller  2) busca o instala Inno Setup  3) arma el instalador
REM El instalador resultante funciona en cualquier PC con Windows 10/11 de 64 bits, SIN Python.
cd /d "%~dp0"

echo ================================================================
echo  [1/3] Creando el ejecutable / Building the executable
echo ================================================================
call crear_exe_windows.bat nopause
if errorlevel 1 goto fail

echo.
echo ================================================================
echo  [2/3] Buscando Inno Setup / Looking for Inno Setup
echo ================================================================
call :findiscc
if not defined ISCC (
    echo Inno Setup no encontrado. Instalando con winget... / Not found. Installing with winget...
    winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
    call :findiscc
)
if not defined ISCC (
    echo.
    echo Instale Inno Setup 6 ^(gratis^) desde / Install Inno Setup 6 ^(free^) from: https://jrsoftware.org/isdl.php
    echo y vuelva a ejecutar este archivo / and run this file again.
    if /i not "%~1"=="nopause" pause
    exit /b 1
)
echo Usando / Using: %ISCC%

for /f "tokens=2 delims==" %%v in ('findstr /b /c:"__version__" taxapp\__init__.py') do set "VER=%%v"
set "VER=%VER: =%"
set "VER=%VER:"=%"
if not defined VER set "VER=1.3.0"

echo.
echo ================================================================
echo  [3/3] Armando el instalador / Building the installer (version %VER%)
echo ================================================================
set "BUILDDIR=%LOCALAPPDATA%\DeclaraFacilUSA_build\dist\DeclaraFacilUSA"
if not exist "%BUILDDIR%\DeclaraFacilUSA.exe" goto fail
"%ISCC%" /Q "/DMyAppVersion=%VER%" "/DBuildDir=%BUILDDIR%" "instalador\DeclaraFacilUSA.iss"
if errorlevel 1 goto fail

echo.
echo Listo / Done: instalador_salida\Instalar_DeclaraFacilUSA_%VER%.exe
echo Copie ese UNICO archivo a cualquier PC y ejecutelo / Copy that ONE file to any PC and run it.
if /i "%~1"=="nopause" exit /b 0
start "" explorer "%~dp0instalador_salida"
pause
exit /b 0

:fail
echo.
echo ERROR: no se pudo crear el instalador / the installer could not be built.
if /i not "%~1"=="nopause" pause
exit /b 1

:findiscc
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%i in ('where iscc 2^>nul') do set "ISCC=%%i"
goto :eof
