#!/usr/bin/env bash
# ==============================================================================
# Aurora OS (Wayland Kiosk Shell - Opcja B)
# Zero X11 • Cage Wayland Compositor • Bezpośredni DRM/KMS • Idealny VSync
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo " 🚀 Aurora OS • Wayland Kiosk Compositor (Cage / Zero X11)       "
echo "=================================================================="

# 1. Konfiguracja katalogu środowiskowego Wayland (XDG_RUNTIME_DIR)
if [ -z "$XDG_RUNTIME_DIR" ] || [ ! -d "$XDG_RUNTIME_DIR" ]; then
    export XDG_RUNTIME_DIR="/tmp/aurora_runtime_$(id -u)"
    mkdir -p "$XDG_RUNTIME_DIR"
    chmod 0700 "$XDG_RUNTIME_DIR"
fi

export XDG_SESSION_TYPE="wayland"
export GDK_BACKEND="wayland"
export CLUTTER_BACKEND="wayland"
export QT_QPA_PLATFORM="wayland"
export SDL_VIDEODRIVER="wayland"
export WEBKIT_FORCE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=0
export LD_LIBRARY_PATH="$SCRIPT_DIR:$LD_LIBRARY_PATH"

# Uprawnienia
chmod +x ./AuroraOS ./TVDecoder_Linux 2>/dev/null || true
chmod +x ./app/*.py 2>/dev/null || true

# 2. Uruchomienie mostka i serwera API w tle (jeśli nie działają)
PORT=8080
if [ -f "./app/tvdecoder_server.py" ] && ! pgrep -f "tvdecoder_server.py" >/dev/null 2>&1; then
    python3 "./app/tvdecoder_server.py" "$PORT" &
fi
if [ -f "./app/apple_tv_bridge.py" ] && ! pgrep -f "apple_tv_bridge.py" >/dev/null 2>&1; then
    python3 "./app/apple_tv_bridge.py" &
fi

# 3. Sprawdzenie obecności kompozytora Cage
if ! command -v cage >/dev/null 2>&1; then
    echo "❌ Nie znaleziono kompozytora Cage!"
    echo "👉 Zainstaluj go poleceniem: sudo apt install cage"
    echo "Uruchamianie w trybie awaryjnym bezpośrednim..."
    if [ -x "./AuroraOS" ]; then
        exec ./AuroraOS
    else
        exec ./TVDecoder_Linux
    fi
fi

# 4. Uruchomienie Kiosku Wayland za pomocą Cage (-s ukrywa kursor)
echo "[Wayland] Startowanie Kiosku Cage z aplikacją Aurora OS..."
if [ -x "./AuroraOS" ]; then
    exec cage -s -- ./AuroraOS
elif [ -x "./TVDecoder_Linux" ]; then
    exec cage -s -- ./TVDecoder_Linux
elif command -v chromium >/dev/null 2>&1; then
    echo "[Wayland] Uruchamianie Chromium w natywnym trybie Ozone Wayland..."
    exec cage -s -- chromium --ozone-platform=wayland --kiosk --app="http://127.0.0.1:8080/" \
        --no-first-run --autoplay-policy=no-user-gesture-required --disable-web-security \
        --enable-gpu-rasterization --enable-zero-copy --user-data-dir="/tmp/aurora_wayland_profile"
else
    echo "❌ Brak aplikacji wykonywalnej Aurora OS ani Chromium!"
    exit 1
fi
