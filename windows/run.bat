@echo off
title LAN Drop Pool
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
echo Uruchamianie aplikacji...
start pythonw lan_drop.py
if %errorlevel% neq 0 (
    echo Uruchamianie w trybie ze standardowa konsola...
    python lan_drop.py
)
