#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Bezprzewodowa Aktualizacja Systemu OTA (Over-The-Air)
# Pobiera najnowsze wydanie/kod z GitHub oraz aktualizuje pakiety systemu Linux
# ==============================================================================

set -e

REPO_URL="https://github.com/mateusz19558/TVDecoder_OS.git"
TARBALL_URL="https://github.com/mateusz19558/TVDecoder_OS/archive/refs/heads/main.tar.gz"
TARGET_DIR="/opt/tvdecoder"
TEMP_DIR="/tmp/tvdecoder_ota_$$"
LOG_FILE="/var/log/tvdecoder_ota.log"
STATUS_FILE="/tmp/ota_status.json"

report_status() {
    local pct="$1"
    local step="$2"
    local desc="$3"
    local is_done="$4"
    local is_err="$5"
    cat <<EOF > "$STATUS_FILE"
{
    "percent": $pct,
    "step": "$step",
    "description": "$desc",
    "completed": ${is_done:-false},
    "error": ${is_err:-false},
    "timestamp": $(date +%s)
}
EOF
}

echo "[OTA] Rozpoczynanie procesu aktualizacji OTA..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 5 "init" "Inicjalizacja środowiska aktualizacji..." false false

mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Krok 1: Pobieranie najnowszego archiwum repozytorium
echo "[OTA 1/5] Pobieranie pakietu aktualizacji z GitHub..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 20 "download" "Pobieranie najnowszych plików Aurora OS z GitHub..." false false

if command -v curl >/dev/null 2>&1; then
    curl -sSL "$TARBALL_URL" -o update.tar.gz
elif command -v wget >/dev/null 2>&1; then
    wget -q "$TARBALL_URL" -O update.tar.gz
else
    echo "[OTA BŁĄD] Brak curl lub wget w systemie!" | tee -a "$LOG_FILE" 2>/dev/null || true
    report_status 20 "error" "Brak narzędzia curl lub wget w systemie!" false true
    exit 1
fi

# Krok 2: Wypakowanie i weryfikacja
echo "[OTA 2/5] Weryfikacja i rozpakowywanie pakietu..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 40 "extract" "Weryfikacja i rozpakowywanie pakietu Aurora OS..." false false

tar -xzf update.tar.gz
EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "TVDecoder_OS-*" | head -n 1)

if [ -z "$EXTRACTED_DIR" ] || [ ! -d "$EXTRACTED_DIR" ]; then
    echo "[OTA BŁĄD] Nieprawidłowy format archiwum aktualizacji!" | tee -a "$LOG_FILE" 2>/dev/null || true
    report_status 40 "error" "Nieprawidłowy format pobranego archiwum!" false true
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Krok 3: Kopiowanie nowych plików aplikacji i konfiguracji do /opt/tvdecoder
echo "[OTA 3/5] Wdrażanie zaktualizowanych plików do $TARGET_DIR..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 60 "install_app" "Wdrażanie plików aplikacji i sterowników..." false false

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
chmod +x "$TARGET_DIR/app/TVDecoder_VB" 2>/dev/null || true
chmod +x "$TARGET_DIR/app"/*.py 2>/dev/null || true
chmod +x "$TARGET_DIR/config"/*.sh 2>/dev/null || true
chmod +x "$TARGET_DIR/scripts"/*.sh 2>/dev/null || true

# Krok 4: Aktualizacja pakietów systemu Linux (Debian / Ubuntu)
echo "[OTA 4/5] Aktualizacja pakietów bezpieczeństwa systemu Linux..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 75 "linux_update" "Aktualizowanie pakietów systemowych Linux (apt-get)..." false false

if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y 2>&1 | tee -a "$LOG_FILE" || true
    apt-get upgrade -y --no-install-recommends 2>&1 | tee -a "$LOG_FILE" || true
    apt-get autoremove -y 2>&1 | tee -a "$LOG_FILE" || true
    apt-get clean 2>&1 | tee -a "$LOG_FILE" || true
fi

# Aktualizacja bibliotek Pythona jeśli wymagane
if command -v pip3 >/dev/null 2>&1; then
    pip3 install --break-system-packages --upgrade HAP-python[QRCode] requests cryptography zeroconf 2>/dev/null || true
fi

# Zapisanie zaktualizowanej sygnatury wersji do version.json
if command -v curl >/dev/null 2>&1; then
    LATEST_COMMIT=$(curl -sSL "https://api.github.com/repos/mateusz19558/TVDecoder_OS/commits/main" 2>/dev/null | grep '"sha":' | head -n 1 | cut -d '"' -f 4 | cut -c 1-7 || true)
    if [ -n "$LATEST_COMMIT" ]; then
        echo "{\"version\": \"3.2.0\", \"commit_sha\": \"$LATEST_COMMIT\", \"build_date\": \"$(date +%Y-%m-%d)\", \"system\": \"Aurora OS (Debian 12 Bookworm Minimal)\"}" > "$TARGET_DIR/app/version.json" 2>/dev/null || true
    fi
fi

# Krok 5: Finalizacja i ewentualny restart usługi
echo "[OTA 5/5] Finalizacja aktualizacji..." | tee -a "$LOG_FILE" 2>/dev/null || true
report_status 95 "finalize" "Finalizacja i przeładowanie usług..." false false

rm -rf "$TEMP_DIR"

if command -v systemctl >/dev/null 2>&1; then
    systemctl restart tvdecoder-kiosk.service 2>/dev/null || true
fi

report_status 100 "done" "System TVDecoder OS oraz pakiety Linux zostały pomyślnie zaktualizowane!" true false
echo "[OTA SUKCES] System TVDecoder OS został zaktualizowany do najnowszej wersji!" | tee -a "$LOG_FILE" 2>/dev/null || true
exit 0
