@echo off
title LAN Drop Pool
setlocal enabledelayedexpansion

:: 1. Jesli skrypt jest wewnatrz folderu projektu
if exist "%~dp0windows\run.bat" (
    cd /d "%~dp0windows"
    call run.bat
    exit /b
)

:: 2. Sprawdz C:\Lan drop pool
if exist "C:\Lan drop pool\windows\run.bat" (
    cd /d "C:\Lan drop pool\windows"
    call run.bat
    exit /b
)

:: 3. Sprawdz C:\LanDropPool
if exist "C:\LanDropPool\windows\run.bat" (
    cd /d "C:\LanDropPool\windows"
    call run.bat
    exit /b
)

:: 4. Sprawdz na Pulpicie
if exist "%USERPROFILE%\Desktop\Lan drop pool\windows\run.bat" (
    cd /d "%USERPROFILE%\Desktop\Lan drop pool\windows"
    call run.bat
    exit /b
)

echo ========================================================
echo [BLAD] Nie znaleziono folderu LAN Drop!
echo Upewnij sie, ze folder 'Lan drop pool' znajduje sie bezposrednio na dysku C:\
echo (sciezka: C:\Lan drop pool\).
echo ========================================================
pause
exit /b 1
