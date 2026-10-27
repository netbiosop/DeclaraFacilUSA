@echo off
REM ==== DeclaraFacil USA - iniciar en Windows / start on Windows ====
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" (where python >nul 2>nul && set PY=python)
if "%PY%"=="" (
    echo No se encontro Python / Python not found: https://www.python.org/downloads/  ^("Add python.exe to PATH"^)
    pause
    exit /b 1
)

REM reportlab es opcional (PDF) / optional (PDF export)
%PY% -c "import reportlab" >nul 2>nul || %PY% -m pip install --user --quiet reportlab
REM pypdf llena los formularios oficiales del IRS / fills the official IRS forms
%PY% -c "import pypdf" >nul 2>nul || %PY% -m pip install --user --quiet pypdf

where pyw >nul 2>nul && (start "" pyw -3 main.py %* & exit /b 0)
where pythonw >nul 2>nul && (start "" pythonw main.py %* & exit /b 0)
%PY% main.py %*
