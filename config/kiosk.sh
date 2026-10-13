#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Kiosk Session Launcher
# ==============================================================================

# 1. Wyłączenie wygaszacza ekranu i zarządzania energią DPMS (telewizor nigdy nie gaśnie)
xset -dpms
xset s off
xset s noblank

# 2. Ukrywanie kursora myszy (pilotem lub po 1 sek. bezczynności)
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 1 -root &
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
sleep 0.5

# 4. Sprawdzenie, czy wybrano tryb instalacji z menu bootloadera
if grep -q "install_mode=1" /proc/cmdline; then
    xterm -fullscreen -bg black -fg white -fa 'Monospace' -fs 14 -e "/opt/tvdecoder/scripts/installer.sh"
    # Po zakończeniu instalatora restartujemy lub wracamy do kiosku
    reboot
    exit 0
fi

# 5. Konfiguracja środowiska Wine
export WINEPREFIX="/home/tvuser/.wine"
export WINEARCH="win64"
export WINEDEBUG="-all"
export DISPLAY=":0"

APP_DIR="/opt/tvdecoder/app"
EXE_PATH="$APP_DIR/TVDecoderApp.exe"

# Jeśli nie ma skompilowanego C#, sprawdzamy C++ TVDecoder
if [ ! -f "$EXE_PATH" ]; then
    EXE_PATH="$APP_DIR/TVDecoder.exe"
fi

cd "$APP_DIR" || exit 1

# 6. Pętla Watchdoga (Kiosk Appliance - dekoder działa nieprzerwanie)
echo "=== Start TVDecoder OS Kiosk ==="
while true; do
    echo "[$(date)] Uruchamianie TVDecoder..."
    wine "$EXE_PATH"
    
    EXIT_CODE=$?
    echo "[$(date)] TVDecoder zakończył działanie z kodem: $EXIT_CODE"
    
    # 2 sekundy pauzy przed ponownym startem w razie crasha
    sleep 2
done
