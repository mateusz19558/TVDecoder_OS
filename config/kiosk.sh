#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Natywna Sesja Pulpitu Smart TV (LightDM Desktop Session)
# 100% Natywny Skompilowany Dekoder (.NET 10 / Avalonia UI / Skia Mesa)
# ==============================================================================

# 0. Zamknięcie Plymouth i wyczyszczenie konsoli
plymouth --quit 2>/dev/null || true

# 1. Wyłączenie wygaszacza ekranu i zarządzania energią DPMS
xset -dpms 2>/dev/null || true
xset s off 2>/dev/null || true
xset s noblank 2>/dev/null || true

# 2. Ukrywanie kursora myszy dopiero po bezczynności (umożliwia obsługę myszką)
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 4 -root &
fi

# 3. Odciszenie i ustawienie głośności audio
if command -v amixer >/dev/null 2>&1; then
    amixer sset Master 100% unmute >/dev/null 2>&1 || true
fi
if command -v pactl >/dev/null 2>&1; then
    pactl set-sink-volume @DEFAULT_SINK@ 100% >/dev/null 2>&1 || true
    pactl set-sink-mute @DEFAULT_SINK@ 0 >/dev/null 2>&1 || true
fi

# 3b. Integracja VMware Tools (automatyczne skalowanie rozdzielczości do pełnego ekranu i płynna mysz)
if command -v vmware-user-suid-wrapper >/dev/null 2>&1; then
    vmware-user-suid-wrapper &
elif command -v vmtoolsd >/dev/null 2>&1; then
    vmtoolsd -n vmusr &
fi
sleep 0.8

# Automatyczne ustawienie rozdzielczości (Full HD / natywna monitora)
if command -v xrandr >/dev/null 2>&1; then
    DISP=$(xrandr | grep " connected" | awk '{print $1}' | head -n 1)
    if [ -n "$DISP" ]; then
        xrandr --output "$DISP" --auto 2>/dev/null || true
    fi
fi

APP_DIR="/opt/tvdecoder/app"
export LD_LIBRARY_PATH="$APP_DIR:$LD_LIBRARY_PATH"
export DOTNET_BUNDLE_EXTRACT_BASE_DIR="/tmp/aurora_bundle"
mkdir -p "$DOTNET_BUNDLE_EXTRACT_BASE_DIR" 2>/dev/null || true

# Uprawnienia do wykonywania
chmod +x "$APP_DIR/AuroraOS" "$APP_DIR/TVDecoder_Linux" "$APP_DIR"/*.py "$APP_DIR"/*.sh 2>/dev/null || true
cd "$APP_DIR" || exit 1

# 4. Uruchomienie menedżera okien Openbox (zarządzanie pełnym ekranem bez obramowania)
if command -v openbox >/dev/null 2>&1; then
    openbox --config-file /opt/tvdecoder/config/rc.xml &
    sleep 0.2
fi

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

# 7. Start aplikacji Aurora OS jako głównego pulpitu
echo "=================================================================="
echo " 🚀 Aurora OS • Główna Sesja Pulpitu Smart TV (Desktop Session)   "
echo "=================================================================="

APP_EXEC="$APP_DIR/AuroraOS"
if [ ! -x "$APP_EXEC" ] && [ -x "$APP_DIR/TVDecoder_Linux" ]; then
    APP_EXEC="$APP_DIR/TVDecoder_Linux"
fi

if [ -x "$APP_EXEC" ]; then
    while true; do
        echo "[$(date)] Uruchamianie pulpitu Aurora OS: $APP_EXEC"
        "$APP_EXEC" >> /tmp/aurora_stdout.log 2>&1
        EXIT_CODE=$?
        echo "[$(date)] Pulpit Aurora OS zakończył działanie (kod: $EXIT_CODE). Restart za 1s..."
        sleep 1
    done
else
    echo "[AuroraOS] BŁĄD: Brak pliku binarnego $APP_EXEC!"
    sleep 10
fi
