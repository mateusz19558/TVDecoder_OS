# 📺 TVDecoder OS - Dedykowany System Operacyjny Set-Top Box (Hybrid ISO)

Bootowalny, hybrydowy obraz systemu operacyjnego (**Live USB + Instalator na dysk**), który zamienia dowolny komputer, laptop czy mini PC (z wyjściem HDMI) w **pełnoprawny dekoder telewizyjny / Smart TV**.

---

## 🌟 Główne cechy systemu

* **100% Natywny Linux (Zero Wine)**:
  - Brak powolnej emulacji Wine, brak zależności 32-bitowych bibliotek.
  - Natywny program linuksowy z bezpośrednim dostępem do GPU (Mesa DRI, Vulkan, VA-API) i minimalnym zużyciem pamięci RAM.
* **Błyskawiczny start (Appliance Mode)**:
  - Brak pulpitu, paska zadań i zbędnych procesów okienkowych.
  - Komputer startuje bezpośrednio do aplikacji TVDecoder na pełnym ekranie z obsługą 4K/60fps HDR.
* **Wbudowane sterowanie Pilotem Apple (iPhone)**:
  - Natywny mostek HomeKit HAP działający w tle.
  - Pilot w Centrum Sterowania iOS na iPhone i iPadzie pozwala na pełną kontrolę TV, EPG, głośności i menu.
* **Tryb Hybrydowy (Live USB + Instalator)**:
  - **Tryb Live**: Uruchamianie bezpośrednio z pendrive'a/RAM bez modyfikowania dysków w komputerze.
  - **Tryb Instalatora**: 1-kliknięciem instaluje TVDecoder OS na stałe na dysku twardym (HDD/SSD/NVMe), zamieniając maszynę w dedykowane urządzenie Smart TV.
* **Wsparcie Sprzętowe (Out-of-the-Box)**:
  - Baza: Debian 12 (Bookworm) Minimal.
  - Pełne sterowniki graficzne z akceleracją sprzętową: Intel, AMD Radeon, Nvidia (Mesa + Vulkan).
  - Dźwięk HDMI (automatycznie odciszony i ustawiony na 100% z obsługą PipeWire/ALSA).
  - Obsługa sieci Wi-Fi i kablowej Ethernet (NetworkManager).
* **Obsługa UEFI oraz BIOS Legacy**:
  - Obsługuje nowoczesne płyty główne z UEFI (Secure Boot off) oraz starsze komputery z BIOS MBR.

---

## 📁 Struktura Projektu

```
TVDecoder_OS/
├── .github/workflows/
│   └── build_iso.yml           # Automatyczne budowanie ISO w chmurze GitHub
├── app/                        # Natywny program TVDecoder Linux (Aurora OS Appliance, Zero Wine)
│   ├── tvdecoder-linux         # Główny natywny program wykonywalny Linuksa (Kiosk Appliance)
│   ├── tvdecoder_server.py     # Wbudowany serwer API i mostek Server-Sent Events dla pilota
│   ├── dekoder_aurora_ui.html  # Pełny koncept interfejsu Aurora OS (HLS Live TV, EPG, VOD)
│   ├── apple_tv_bridge.py      # Mostek Apple TV HomeKit (sterowanie z iPhone)
│   ├── channels.json           # Baza kanałów telewizyjnych (10 stacji HD/4K)
│   ├── apple_remote_qr.png     # Kod QR parowania z aplikacją Dom (Apple Home)
│   └── accessory.state         # Stan parowania HomeKit
├── config/
│   ├── grub.cfg                # Menu startowe UEFI
│   ├── isolinux.cfg            # Menu startowe BIOS/Legacy
│   ├── kiosk.sh                # Natywny skrypt środowiska Kiosk & Watchdog (Zero Wine)
│   └── tvdecoder-kiosk.service # Usługa systemd autologinu do TVDecoder
├── scripts/
│   ├── build_iso.sh            # Główny skrypt tworzący obraz TVDecoderOS.iso
│   ├── build_with_docker.bat   # Budowanie przez Docker na Windows
│   ├── build_with_wsl.bat      # Budowanie przez WSL na Windows
│   ├── Dockerfile              # Izolowane środowisko budujące
│   └── installer.sh            # Skrypt instalatora na dysk
└── README.md
```

---

## 🚀 Jak zbudować plik ISO (`TVDecoderOS.iso`)

Dostępne są 3 wygodne sposoby wygenerowania obrazu:

### Opcja 1: W chmurze przez GitHub Actions (Najprostsza, 0 instalacji)
1. Wrzuć folder projektu do swojego repozytorium GitHub.
2. Wejdź w zakładkę **Actions** i uruchom workflow **`Build TVDecoder OS ISO`**.
3. Po ok. 4 minutach pobierz gotowy plik **`TVDecoderOS.iso`** z sekcji *Artifacts*.

### Opcja 2: Lokalnie przez Docker (Windows)
1. Upewnij się, że masz uruchomiony Docker Desktop.
2. Uruchom dwuklikiem plik:
   👉 **`scripts\build_with_docker.bat`**
3. Po zakończeniu skryptu w głównym katalogu pojawi się plik **`TVDecoderOS.iso`**.

### Opcja 3: Lokalnie na maszynie z Linuksem / Debian / WSL
W terminalu z uprawnieniami roota wykonaj:
```bash
sudo chmod +x scripts/build_iso.sh
sudo ./scripts/build_iso.sh
```

---

## 💾 Nagrywanie na Pendrive USB

Po wygenerowaniu pliku `TVDecoderOS.iso`:
1. **Rufus (Windows)**:
   - Wybierz swój pendrive.
   - Wskaż plik `TVDecoderOS.iso`.
   - Schemat partycjonowania: **GPT** (dla UEFI) lub **MBR** (dla starszych płyt).
   - Kliknij *Start*.
2. **Ventoy**:
   - Skopiuj plik `TVDecoderOS.iso` bezpośrednio na pendrive z Ventoyem.

---

## 🎮 Sterowanie Dekoderem (Pilot / Klawiatura)

| Klawisz | Funkcja |
|---|---|
| **▲ / ▼** lub **W / S** | Zmiana kanału (`CH+` / `CH-`) |
| **0 – 9** | Wybór kanału numerem |
| **ENTER** / **I** | Dolny pasek informacyjny (Info Banner) |
| **E** / **L** | Przewodnik programowy EPG / Lista kanałów |
| **F2** lub **ESC** | **YouTube Smart TV (Oficjalny Cobalt / Leanback)** – przełącza TV ⟷ YouTube |
| **Alt + ESC** | Natychmiastowy powrót z YouTube do kanałów TV |
| **◄ / ►** / **+ / -** | Regulacja głośności |
| **M** | Wyciszenie dźwięku (MUTE) |
| **SPACJA** | Pauza / Play |
| **F11** | Pełny ekran |
