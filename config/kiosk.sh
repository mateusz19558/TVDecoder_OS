#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Pancerne Środowisko Kiosk Appliance (X11 Universal Mode)
# 100% Natywny Skompilowany Dekoder TV (.NET 10 / Avalonia UI / Skia Mesa)
# Zero Wine • Zero Chromium • Zero WebKit
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

# Uprawnienia do wykonywania
chmod +x "$APP_DIR/AuroraOS" "$APP_DIR/TVDecoder_Linux" "$APP_DIR"/*.py 2>/dev/null || true
cd "$APP_DIR" || exit 1

# 4. Menedżer okien Openbox dla obsługi pełnego ekranu i pilota
openbox --config-file /opt/tvdecoder/config/rc.xml &
sleep 0.3

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

# 7. Start natywnego skompilowanego programu Aurora OS (.NET 10 Linux x64)
echo "=================================================================="
echo " 🚀 Aurora OS • Start Natywnej Aplikacji Dekodera TV (Linux x64)   "
echo "=================================================================="

APP_EXEC="$APP_DIR/AuroraOS"
if [ ! -x "$APP_EXEC" ] && [ -x "$APP_DIR/TVDecoder_Linux" ]; then
    APP_EXEC="$APP_DIR/TVDecoder_Linux"
fi

if [ -x "$APP_EXEC" ]; then
    while true; do
        echo "[$(date)] Uruchamianie skompilowanego dekodera: $APP_EXEC"
        "$APP_EXEC" >> /tmp/aurora_stdout.log 2>&1
        EXIT_CODE=$?
        echo "[$(date)] Aplikacja zakończyła działanie (kod: $EXIT_CODE). Restart za 1s..."
        sleep 1
    done
else
    echo "[AuroraOS] BŁĄD: Brak pliku binarnego $APP_EXEC!"
    sleep 10
fi
