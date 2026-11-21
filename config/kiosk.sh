#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Pancerne Środowisko Kiosk Appliance (X11 Universal Mode)
# 100% kompatybilny ze wszystkimi GPU, PC oraz maszynami wirtualnymi (VMware/VBox)
# ==============================================================================

# 0. Zamknięcie splash screena Plymouth i wyczyszczenie konsoli
plymouth --quit 2>/dev/null || true
clear > /dev/tty1 2>/dev/null || true

# 1. Wyłączenie wygaszacza ekranu i zarządzania energią DPMS
xset -dpms 2>/dev/null || true
xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true

# 2. Ukrywanie kursora myszy
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.1 -root &
fi

# 3. Odciszenie i ustawienie głośności audio
if command -v amixer >/dev/null 2>&1; then
    amixer sset Master 100% unmute >/dev/null 2>&1 || true
fi
if command -v pactl >/dev/null 2>&1; then
    pactl set-sink-volume @DEFAULT_SINK@ 100% >/dev/null 2>&1 || true
    pactl set-sink-mute @DEFAULT_SINK@ 0 >/dev/null 2>&1 || true
fi

APP_DIR="/opt/tvdecoder/app"
export DISPLAY=":0"
export XDG_SESSION_TYPE="x11"
export LD_LIBRARY_PATH="$APP_DIR:$LD_LIBRARY_PATH"

# Wykrywanie maszyn wirtualnych (VMware, VirtualBox, QEMU)
IS_VIRTUAL_MACHINE=0
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt -q; then
    IS_VIRTUAL_MACHINE=1
    echo "[AuroraOS] Wykryto środowisko wirtualne (VMware / VirtualBox)."
    export WEBKIT_DISABLE_COMPOSITING_MODE=1
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export LIBGL_ALWAYS_SOFTWARE=1
fi

# Uprawnienia do wykonywania
chmod +x "$APP_DIR/AuroraOS" "$APP_DIR/TVDecoder_Linux" "$APP_DIR/tvdecoder-linux" "$APP_DIR"/*.py 2>/dev/null || true
cd "$APP_DIR" || exit 1

# 4. Menedżer okien Openbox dla obsługi pełnego ekranu i pilota
openbox --config-file /opt/tvdecoder/config/rc.xml &
sleep 0.2

# 5. Sprawdzenie trybu instalacji na dysku
if grep -q "install_mode=1" /proc/cmdline; then
    xterm -fullscreen -bg black -fg white -fa 'Monospace' -fs 14 -e "/opt/tvdecoder/scripts/installer.sh"
    reboot
    exit 0
fi

# 6. Uruchomienie mostka Apple TV w tle
if [ -f "$APP_DIR/apple_tv_bridge.py" ] && ! pgrep -f "apple_tv_bridge.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/apple_tv_bridge.py" &
fi

# 7. Uruchomienie wbudowanego serwera API / Web
if [ -f "$APP_DIR/tvdecoder_server.py" ] && ! pgrep -f "tvdecoder_server.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/tvdecoder_server.py" 8080 &
fi

# 8. Oczekiwanie na gotowość serwera aplikacji (max 5 sekund)
echo "[AuroraOS] Oczekiwanie na start serwera aplikacji na porcie 8080..."
for i in $(seq 1 25); do
    if curl -s -I "http://127.0.0.1:8080/" >/dev/null 2>&1; then
        echo "[AuroraOS] Serwer HTTP aktywny i gotowy."
        break
    fi
    sleep 0.2
done

# Funkcja uruchamiająca Chromium w dedykowanym trybie Kiosk Smart TV
start_chromium_kiosk() {
    echo "[AuroraOS] Uruchamianie sprawdzonego silnika Kiosk Chromium..."
    CHROMIUM_BIN="chromium"
    if ! command -v "$CHROMIUM_BIN" >/dev/null 2>&1; then
        if command -v chromium-browser >/dev/null 2>&1; then
            CHROMIUM_BIN="chromium-browser"
        elif command -v google-chrome >/dev/null 2>&1; then
            CHROMIUM_BIN="google-chrome"
        fi
    fi

    FLAGS=(
        "--kiosk"
        "--app=http://127.0.0.1:8080/"
        "--no-first-run"
        "--no-default-browser-check"
        "--disable-infobars"
        "--disable-session-crashed-bubble"
        "--disable-features=Translate"
        "--disable-translate"
        "--lang=pl-PL"
        "--autoplay-policy=no-user-gesture-required"
        "--disable-web-security"
        "--allow-running-insecure-content"
        "--user-data-dir=/home/tvuser/.config/aurora_kiosk_profile"
    )

    if [ "$IS_VIRTUAL_MACHINE" -eq 1 ]; then
        FLAGS+=(
            "--disable-gpu-compositing"
            "--disable-software-rasterizer"
        )
    else
        FLAGS+=(
            "--enable-gpu-rasterization"
            "--enable-zero-copy"
            "--ignore-gpu-blocklist"
        )
    fi

    while true; do
        "$CHROMIUM_BIN" "${FLAGS[@]}"
        echo "[AuroraOS] Restart sesji awaryjnej Kiosk..."
        sleep 1
    done
}

# 9. Start natywnego skompilowanego programu Aurora OS (.NET 10 Linux x64)
echo "=== Start Skompilowanego Programu Aurora OS (Natywna Aplikacja Linux) ==="

APP_EXEC="$APP_DIR/AuroraOS"
if [ ! -x "$APP_EXEC" ] && [ -x "$APP_DIR/TVDecoder_Linux" ]; then
    APP_EXEC="$APP_DIR/TVDecoder_Linux"
fi

if [ -x "$APP_EXEC" ]; then
    echo "[$(date)] Uruchamianie skompilowanej aplikacji Linux: $APP_EXEC"
    START_T=$(date +%s)
    "$APP_EXEC"
    EXIT_CODE=$?
    ELAPSED=$(( $(date +%s) - START_T ))
    echo "[$(date)] Aplikacja Aurora OS zakończyła działanie po ${ELAPSED}s z kodem: $EXIT_CODE"

    if [ "$ELAPSED" -ge 4 ]; then
        while true; do
            "$APP_EXEC"
            sleep 1
        done
    else
        echo "[AuroraOS] Silnik natywny nie zdołał utrzymać okna pod obecnym sterownikiem graficznym (${ELAPSED}s)."
        echo "[AuroraOS] Uruchamianie wbudowanego trybu Kiosk Smart TV (czyste okno bez dymków i elementów przeglądarki)..."
        start_chromium_kiosk
    fi
else
    echo "[AuroraOS] Ostrzeżenie: Brak skompilowanego pliku binarnego. Uruchamianie silnika Smart TV."
    start_chromium_kiosk
fi
