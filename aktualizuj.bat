@echo off
chcp 65001 >nul
title Aktualizator LAN Drop
echo ========================================================
echo          AKTUALIZATOR LAN DROP POOL
echo ========================================================
echo.

:: 1. Ustal katalog docelowy LAN Drop
set "TARGET_DIR=C:\Lan drop pool"
if not exist "%TARGET_DIR%\windows" (
    if exist "%USERPROFILE%\Desktop\Lan drop pool\windows" (
        set "TARGET_DIR=%USERPROFILE%\Desktop\Lan drop pool"
    ) else if exist "%~dp0windows" (
        set "TARGET_DIR=%~dp0"
    )
)

echo Zamykanie dzialajacego programu LAN Drop...
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Kopiowanie nowej wersji do: %TARGET_DIR% ...
robocopy "%~dp0." "%TARGET_DIR%" /E /XD .git __pycache__ .venv /XF landrop_update.zip /R:3 /W:1 >nul 2>&1
if %errorlevel% geq 8 (
    xcopy /s /y /q /i /r /h "%~dp0*" "%TARGET_DIR%\" >nul 2>&1
)

echo.
echo ========================================================
echo      SUKCES: Program zostal zaktualizowany!
echo ========================================================
echo Uruchamianie nowej wersji LAN Drop...
cd /d "%TARGET_DIR%\windows"
if exist "run.bat" (
    start run.bat
) else (
    start pythonw lan_drop.py
)
timeout /t 2 /nobreak >nul
exit
