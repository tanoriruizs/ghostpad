@echo off
setlocal
title GhostPad
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

where py >nul 2>&1 || (
    echo [ERROR] No se encontro Python. Instalalo desde https://python.org
    echo         Marca la casilla "Add python.exe to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo Creando entorno virtual...
    py -3 -m venv "%VENV%" || (echo [ERROR] No se pudo crear el entorno virtual. & pause & exit /b 1)
    "%PY%" -m pip install --upgrade pip --quiet
    echo Instalando dependencias...
    "%PY%" -m pip install -r requirements.txt || (echo [ERROR] Fallo la instalacion. & pause & exit /b 1)
)

"%PY%" server.py --players 2 --port 8000
pause
