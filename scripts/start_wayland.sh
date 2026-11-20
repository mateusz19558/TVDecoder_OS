#!/usr/bin/env bash
# ==============================================================================
# Aurora OS (Wayland Kiosk Shell - Opcja B)
# Zero X11 • Cage Wayland Compositor • Bezpośredni DRM/KMS • Idealny VSync
# ==============================================================================
set -e

# Zamknięcie splash screena Plymouth
plymouth --quit 2>/dev/null || true

BASE_DIR="/opt/tvdecoder"
APP_DIR="$BASE_DIR/app"

if [ ! -d "$APP_DIR" ]; then
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../app" && pwd)"
fi

cd "$APP_DIR" || exit 1

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
export LD_LIBRARY_PATH="$APP_DIR:$LD_LIBRARY_PATH"

# Uprawnienia wykonywalne
chmod +x "$APP_DIR/AuroraOS" "$APP_DIR/TVDecoder_Linux" "$APP_DIR"/*.py 2>/dev/null || true

# 2. Uruchomienie mostka i serwera API w tle (jeśli nie działają)
PORT=8080
if [ -f "$APP_DIR/tvdecoder_server.py" ] && ! pgrep -f "tvdecoder_server.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/tvdecoder_server.py" "$PORT" &
fi
if [ -f "$APP_DIR/apple_tv_bridge.py" ] && ! pgrep -f "apple_tv_bridge.py" >/dev/null 2>&1; then
    python3 "$APP_DIR/apple_tv_bridge.py" &
fi

SERVER_URL="http://127.0.0.1:${PORT}/"

# 3. Oczekiwanie na serwer API
echo "[Wayland] Oczekiwanie na gotowość serwera: $SERVER_URL..."
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL" 2>/dev/null | grep -q "200\|404"; then
        break
    fi
    sleep 0.1
done

# 4. Sprawdzenie obecności kompozytora Cage
if ! command -v cage >/dev/null 2>&1; then
    echo "❌ Nie znaleziono kompozytora Cage, uruchamianie bezpośrednie..."
    if [ -x "$APP_DIR/AuroraOS" ]; then
        exec "$APP_DIR/AuroraOS"
    elif [ -x "$APP_DIR/TVDecoder_Linux" ]; then
        exec "$APP_DIR/TVDecoder_Linux"
    fi
fi

# 5. Uruchomienie Kiosku Wayland za pomocą Cage (-s ukrywa kursor) ze skompilowaną aplikacją
echo "[Wayland] Startowanie Kiosku Cage dla Aurora OS (Natywna Aplikacja Linux)..."

APP_EXEC="$APP_DIR/AuroraOS"
if [ ! -x "$APP_EXEC" ] && [ -x "$APP_DIR/TVDecoder_Linux" ]; then
    APP_EXEC="$APP_DIR/TVDecoder_Linux"
fi

if [ -x "$APP_EXEC" ]; then
    exec cage -s -- "$APP_EXEC"
else
    echo "[Wayland] Brak aplikacji wykonywalnej AuroraOS!"
    exit 1
fi
