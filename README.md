# ⚡ LAN DROP

Nowoczesny, minimalistyczny system błyskawicznej wymiany plików w sieci lokalnej (LAN / Wi-Fi).

Zaprojektowany w stylistyce **Pure Black (OLED Stealth)**, wolny od zbędnych procesów, bez limitów rozmiaru i z pełną przepustowością Twojego łącza (do 100–120 MB/s przez router Orange FunBox lub Hotspot).

---

## 🎯 Dwa tryby współpracy z telefonem

Aplikacja oferuje dwa niezależne, wygodne tryby:

### 1. Szybki zrzut (QR / Web) — Działa natychmiast, bez instalowania aplikacji!
* **Dla kogo**: Dla Ciebie, znajomych, rodziny lub dowolnego innego telefonu w 3 sekundy.
* **Jak to działa**:
  1. Na komputerze klikasz przycisk **`📱 Szybki zrzut (QR)`**.
  2. Telefonem skanujesz kod QR aparatem (lub wchodzisz na adres `http://<IP-komputera>:50505`).
  3. Otwiera się mobilna wrzutnia w przeglądarce:
     - Możesz pobierać pliki wystawione z komputera.
     - Możesz wysyłać zdjęcia, filmy i dokumenty z galerii telefonu prosto do folderu *Pobrane* na komputerze.

### 2. Dedykowana aplikacja APK (Wspólna Wisząca Pula LAN)
* **Dla kogo**: Gdy chcesz mieć aplikację na telefonie i np. dwóch komputerach, gdzie pliki wiszą w puli sieciowej i czekają na pobranie.
* **Jak to działa**:
  1. Otwierasz aplikację na telefonie i dodajesz pliki z Galerii lub Menedżera plików.
  2. Pliki **wiszą w sieci lokalnej** — pojawiają się automatycznie na ekranach wszystkich Twoich komputerów.
  3. Pobierasz je na dowolnym komputerze wtedy, kiedy chcesz.
  4. Po zamknięciu aplikacji na telefonie pliki natychmiast znikają z widoku w sieci (pełna ulotność).

---

## 📶 Praca poza domem / na uczelni (Hotspot Wi-Fi)

1. Na laptopie klikasz przycisk **`📶 Hotspot Wi-Fi`**.
2. Laptop uruchamia punkt dostępu, **nie rozłączając się z Wi-Fi uczelni**!
3. Twój telefon (np. Samsung Galaxy A36) po włączeniu Wi-Fi łączy się z laptopem automatycznie (po pierwszym sparowaniu) lub przez zeskanowanie kodu QR.

---

## 🚀 Uruchomienie na komputerze (Windows)

1. Wejdź do folderu `windows/`.
2. Kliknij dwukrotnie plik **`run.bat`**.
3. Aplikacja sprawdzi środowisko, doinstaluje wymagane biblioteki i otworzy interfejs w czerni OLED.

---

## 📱 Kompilacja pliku APK na telefon (GitHub Actions)

Projekt w folderze `android/` zawiera gotowy workflow **GitHub Actions** (`.github/workflows/build-apk.yml`). Nie musisz instalować Android Studio:

1. Utwórz nowe repozytorium na swoim koncie GitHub (np. `lan-drop`).
2. Wypchnij projekt na GitHuba:
   ```bash
   git init
   git add .
   git commit -m "LAN Drop OLED"
   git branch -M main
   git remote add origin https://github.com/<twoj-login>/lan-drop.git
   git push -u origin main
   ```
3. Otwórz repozytorium na GitHubie ➔ przejdź do zakładki **Actions**.
4. Po około 2 minutach zadanie zakończy się na zielono — na dole w sekcji **Artifacts** pobierz plik **`LanDropPool-Android-APK`** bezpośrednio na telefon!
