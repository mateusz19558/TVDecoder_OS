#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Kiosk Session Launcher
# ==============================================================================

# 0. Wyciszenie konsoli i ustawienie ciemnego tła ekranu
clear > /dev/tty1 2>/dev/null || true
if command -v xsetroot >/dev/null 2>&1; then
    xsetroot -solid "#080d1a" 2>/dev/null || true
fi

# 1. Wyłączenie wygaszacza ekranu i zarządzania energią DPMS (telewizor nigdy nie gaśnie)
xset -dpms 2>/dev/null || true
xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true

# 2. Ukrywanie kursora myszy (pilotem lub natychmiast)
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.1 -root &
fi

# 3. Odciszenie i ustawienie głośności audio (HDMI / wyjście domyślne)
if command -v amixer >/dev/null 2>&1; then
    amixer sset Master 100% unmute >/dev/null 2>&1 || true
fi
if command -v pactl >/dev/null 2>&1; then
    pactl set-sink-volume @DEFAULT_SINK@ 100% >/dev/null 2>&1 || true
    pactl set-sink-mute @DEFAULT_SINK@ 0 >/dev/null 2>&1 || true
fi

# 3b. Uruchomienie menedżera okien Openbox (dla obsługi skrótów pilota, YouTube TV i trybu fullscreen)
openbox --config-file /opt/tvdecoder/config/rc.xml &
sleep 0.2

# 3c. Natychmiastowy pełnoekranowy ekran ładowania Aurora OS (Splash Screen)
if [ -f "/opt/tvdecoder/app/aurora_splash.py" ]; then
    python3 /opt/tvdecoder/app/aurora_splash.py &
fi

# 4. Sprawdzenie, czy wybrano tryb instalacji z menu bootloadera
if grep -q "install_mode=1" /proc/cmdline; then
    xterm -fullscreen -bg black -fg white -fa 'Monospace' -fs 14 -e "/opt/tvdecoder/scripts/installer.sh"
    # Po zakończeniu instalatora restartujemy lub wracamy do kiosku
    reboot
    exit 0
fi

# 5. Konfiguracja środowiska graficznego (Zero Wine)
export DISPLAY=":0"
export XDG_SESSION_TYPE="x11"

APP_DIR="/opt/tvdecoder/app"
export LD_LIBRARY_PATH="$APP_DIR:$LD_LIBRARY_PATH"
export WEBKIT_FORCE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=0

# Uprawnienia do wykonywania
chmod +x "$APP_DIR/TVDecoder_Linux" "$APP_DIR/tvdecoder-linux" "$APP_DIR"/*.py 2>/dev/null || true

cd "$APP_DIR" || exit 1

# Uruchomienie mostka pilota Apple TV w tle
if [ -f "$APP_DIR/apple_tv_bridge.py" ]; then
    python3 "$APP_DIR/apple_tv_bridge.py" &
fi

# Uruchomienie wbudowanego serwera API (dla sterowania i OTA)
if [ -f "$APP_DIR/tvdecoder_server.py" ]; then
    python3 "$APP_DIR/tvdecoder_server.py" &
fi

# 6. Pętla Watchdoga dla natywnej aplikacji Linux (Zero Wine)
echo "=== Start TVDecoder Linux Native Edition (Zero Wine) ==="
while true; do
    echo "[$(date)] Uruchamianie natywnej aplikacji TVDecoder_Linux..."
    if [ -x "$APP_DIR/TVDecoder_Linux" ]; then
        "$APP_DIR/TVDecoder_Linux"
    elif [ -x "$APP_DIR/tvdecoder-linux" ]; then
        "$APP_DIR/tvdecoder-linux"
    else
        echo "[BLAD] Brak pliku wykonywalnego TVDecoder_Linux!"
        sleep 5
    fi
    
    EXIT_CODE=$?
    echo "[$(date)] TVDecoder zakończył działanie z kodem: $EXIT_CODE"
    sleep 2
done

