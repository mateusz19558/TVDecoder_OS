#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Bezprzewodowa Aktualizacja Systemu OTA (Over-The-Air)
# Pobiera najnowsze wydanie/kod z repozytorium GitHub i aktualizuje dekoder
# ==============================================================================

set -e

REPO_URL="https://github.com/mateusz19558/TVDecoder_OS.git"
TARBALL_URL="https://github.com/mateusz19558/TVDecoder_OS/archive/refs/heads/main.tar.gz"
TARGET_DIR="/opt/tvdecoder"
TEMP_DIR="/tmp/tvdecoder_ota_$$"
LOG_FILE="/var/log/tvdecoder_ota.log"

echo "[OTA] Rozpoczynanie procesu aktualizacji OTA..." | tee -a "$LOG_FILE" 2>/dev/null || echo "[OTA] Start..."

mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Krok 1: Pobieranie najnowszego archiwum repozytorium
echo "[OTA 1/4] Pobieranie pakietu aktualizacji z GitHub..." | tee -a "$LOG_FILE" 2>/dev/null || true
if command -v curl >/dev/null 2>&1; then
    curl -sSL "$TARBALL_URL" -o update.tar.gz
elif command -v wget >/dev/null 2>&1; then
    wget -q "$TARBALL_URL" -O update.tar.gz
else
    echo "[OTA BŁĄD] Brak curl lub wget w systemie!"
    exit 1
fi

# Krok 2: Wypakowanie i weryfikacja
echo "[OTA 2/4] Weryfikacja i rozpakowywanie pakietu..." | tee -a "$LOG_FILE" 2>/dev/null || true
tar -xzf update.tar.gz
EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "TVDecoder_OS-*" | head -n 1)

if [ -z "$EXTRACTED_DIR" ] || [ ! -d "$EXTRACTED_DIR" ]; then
    echo "[OTA BŁĄD] Nieprawidłowy format archiwum aktualizacji!"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Krok 3: Kopiowanie nowych plików aplikacji i konfiguracji do /opt/tvdecoder
echo "[OTA 3/4] Wdrażanie zaktualizowanych plików do $TARGET_DIR..." | tee -a "$LOG_FILE" 2>/dev/null || true
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/config" "$TARGET_DIR/scripts"

if [ -d "$EXTRACTED_DIR/app" ]; then
    cp -ru "$EXTRACTED_DIR/app"/* "$TARGET_DIR/app/" 2>/dev/null || true
fi

if [ -d "$EXTRACTED_DIR/config" ]; then
    cp -ru "$EXTRACTED_DIR/config"/* "$TARGET_DIR/config/" 2>/dev/null || true
fi

if [ -d "$EXTRACTED_DIR/scripts" ]; then
    cp -ru "$EXTRACTED_DIR/scripts"/* "$TARGET_DIR/scripts/" 2>/dev/null || true
fi

# Nadanie uprawnień wykonywalnych
chmod +x "$TARGET_DIR/app/tvdecoder-linux" 2>/dev/null || true
chmod +x "$TARGET_DIR/app"/*.py 2>/dev/null || true
chmod +x "$TARGET_DIR/config"/*.sh 2>/dev/null || true
chmod +x "$TARGET_DIR/scripts"/*.sh 2>/dev/null || true

# Krok 4: Czyszczenie i ewentualny restart usługi
echo "[OTA 4/4] Finalizacja aktualizacji..." | tee -a "$LOG_FILE" 2>/dev/null || true
rm -rf "$TEMP_DIR"

if command -v systemctl >/dev/null 2>&1; then
    systemctl restart tvdecoder-kiosk.service 2>/dev/null || true
fi

echo "[OTA SUKCES] System TVDecoder OS został zaktualizowany do najnowszej wersji!" | tee -a "$LOG_FILE" 2>/dev/null || true
exit 0
