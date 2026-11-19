#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Kiosk Session Launcher (X11 Appliance Mode)
# 100% kompatybilny ze wszystkimi GPU i maszynami wirtualnymi (VMware / VBox / PC)
# ==============================================================================

# 0. Zamknięcie splash screena Plymouth i wyczyszczenie konsoli
plymouth --quit 2>/dev/null || true
clear > /dev/tty1 2>/dev/null || true

if command -v xsetroot >/dev/null 2>&1; then
    xsetroot -solid "#080d1a" 2>/dev/null || true
fi

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
# W maszynach wirtualnych wyłączamy compositing WebKitGTK, aby uniknąć problemów ze sterownikiem vmwgfx
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt -q; then
    echo "[AuroraOS] Wykryto maszynę wirtualną. Uruchamianie bezpiecznego renderowania."
    export WEBKIT_DISABLE_COMPOSITING_MODE=1
    export WEBKIT_DISABLE_DMABUF_RENDERER=1
    export LIBGL_ALWAYS_SOFTWARE=1
else
    export WEBKIT_FORCE_COMPOSITING_MODE=1
    export WEBKIT_DISABLE_COMPOSITING_MODE=0
fi

# Uprawnienia do wykonywania
chmod +x "$APP_DIR/AuroraOS" "$APP_DIR/TVDecoder_Linux" "$APP_DIR/tvdecoder-linux" "$APP_DIR"/*.py 2>/dev/null || true
cd "$APP_DIR" || exit 1

# 3b. Menedżer okien Openbox dla obsługi pełnego ekranu i pilota
openbox --config-file /opt/tvdecoder/config/rc.xml &
sleep 0.2

# 3c. Ekran ładowania Aurora OS
if [ -f "$APP_DIR/aurora_splash.py" ]; then
    python3 "$APP_DIR/aurora_splash.py" &
fi

# 4. Sprawdzenie trybu instalacji
if grep -q "install_mode=1" /proc/cmdline; then
    xterm -fullscreen -bg black -fg white -fa 'Monospace' -fs 14 -e "/opt/tvdecoder/scripts/installer.sh"
    reboot
    exit 0
fi

# 5. Uruchomienie mostka Apple TV w tle
if [ -f "$APP_DIR/apple_tv_bridge.py" ] && ! pgrep -f "apple_tv_bridge.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/apple_tv_bridge.py" &
fi

# 6. Uruchomienie wbudowanego serwera API
if [ -f "$APP_DIR/tvdecoder_server.py" ] && ! pgrep -f "tvdecoder_server.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/tvdecoder_server.py" 8080 &
fi

# 7. Pętla Watchdoga dla aplikacji Aurora OS
echo "=== Start Aurora OS Linux Native Kiosk ==="
while true; do
    echo "[$(date)] Uruchamianie Aurora OS..."
    if [ -x "$APP_DIR/AuroraOS" ]; then
        "$APP_DIR/AuroraOS"
    elif [ -x "$APP_DIR/TVDecoder_Linux" ]; then
        "$APP_DIR/TVDecoder_Linux"
    elif [ -x "$APP_DIR/tvdecoder-linux" ]; then
        "$APP_DIR/tvdecoder-linux"
    elif command -v chromium >/dev/null 2>&1; then
        chromium --kiosk --app="http://127.0.0.1:8080/" --no-first-run --autoplay-policy=no-user-gesture-required
    else
        echo "[BLAD] Brak aplikacji wykonywalnej Aurora OS!"
        sleep 5
    fi
    
    EXIT_CODE=$?
    echo "[$(date)] Aurora OS zakończył działanie z kodem: $EXIT_CODE"
    sleep 2
done
