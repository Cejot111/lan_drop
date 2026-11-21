@echo off
title LAN Drop Pool
cd /d "%~dp0"
echo ========================================================
echo        LAN Drop Pool - Szybki Transfer Lokalny
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [BLAD] Python nie jest zainstalowany lub nie ma go w zmiennej PATH!
    echo Pobierz Pythona z https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Sprawdzanie i instalowanie wymaganych bibliotek...
pip install -r requirements.txt

echo.
echo Zamykanie ewentualnych starych procesow LAN Drop...
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo Uruchamianie aplikacji LAN Drop...
start "" pythonw lan_drop.py
exit /b 0
