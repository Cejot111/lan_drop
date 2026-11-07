@echo off
title Wyslij na GitHub - LAN Drop
cd /d "%~dp0"
echo ========================================================
echo        Wysylanie projektu na Twojego GitHuba
echo  Repozytorium: https://github.com/Cejot111/lan_drop.git
echo ========================================================
echo.
echo 1. Przygotowywanie zmian...
git add .
git commit -m "Dwukierunkowa synchronizacja, udostepnianie linkow i obsluga menu Udostepnij na Androidzie"
echo.
echo 2. Wysylanie kodu na GitHub...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  SUKCES! Kod zostal pomyslnie wyslany na GitHub.
    echo.
    echo  GitHub Actions automatycznie rozpoczal kompilacje nowego APK (v1.1.0)!
    echo  Przejdz do zakladki 'Actions' w swoim repozytorium:
    echo  https://github.com/Cejot111/lan_drop/actions
    echo.
    echo  Gdy zadanie sie zakonczy (zielony ptaszek), kliknij je
    echo  i pobierz plik z sekcji 'Artifacts'.
    echo ========================================================
) else (
    echo.
    echo [BLAD] Wystapil blad podczas wysylania.
    echo Jesli pojawilo sie okno logowania, potwierdz autoryzacje w przegladarce.
)
echo.
pause
