@echo off
:: Permite que los telefonos de la red local lleguen al puerto 8000.
:: Ejecutar como administrador (clic derecho -> Ejecutar como administrador).
title GhostPad - regla de firewall

net session >nul 2>&1 || (
    echo [ERROR] Ejecuta este archivo como ADMINISTRADOR.
    pause
    exit /b 1
)

netsh advfirewall firewall delete rule name="GhostPad" >nul 2>&1
netsh advfirewall firewall add rule name="GhostPad" dir=in action=allow ^
    protocol=TCP localport=8000 profile=private,domain

echo.
echo Regla creada: TCP 8000 permitido en redes privadas.
pause
