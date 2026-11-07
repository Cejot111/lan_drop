@echo off
title Wyslij na GitHub - LAN Drop
cd /d "%~dp0"
echo ========================================================
echo        Wysylanie projektu na Twojego GitHuba
echo  Repozytorium: https://github.com/Cejot111/lan_drop.git
echo ========================================================
echo.
echo Wysylanie kodu...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  SUKCES! Kod zostal pomyslnie wyslany na GitHub.
    echo.
    echo  GitHub sam automatycznie rozpoczal kompilacje pliku APK!
    echo  Przejdz do zakladki 'Actions' w swoim repozytorium:
    echo  https://github.com/Cejot111/lan_drop/actions
    echo ========================================================
) else (
    echo.
    echo [BLAD] Wystapil blad podczas wysylania.
    echo Jesli pojawilo sie okno logowania, potwierdz autoryzacje w przegladarce.
)
echo.
pause
