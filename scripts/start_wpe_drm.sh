#!/usr/bin/env bash
# ==============================================================================
# Aurora OS (WPE WebKit Direct DRM/KMS - Opcja C)
# Zero X11 • Zero Wayland • 100% Direct Embedded Linux DRM/KMS Framebuffer
# Standard przemysłowy Set-Top Box (Sky TV, Comcast, RDK, webOS)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo " ⚡ Aurora OS • WPE WebKit Direct DRM/KMS Appliance (Opcja C)     "
echo " Zero X11 • Zero Wayland • Bezpośredni bufor karty graficznej GPU  "
echo "=================================================================="

# 1. Konfiguracja zmiennych środowiskowych WPE / Mesa DRM
export COG_PLATFORM_NAME="drm"
export WPE_BACKEND="fdo"
export WPE_FORCE_COMPOSITING_MODE=1
export GST_VAAPI_ALL_DRIVERS=1

# Uprawnienia
chmod +x ./app/*.py 2>/dev/null || true

# 2. Uruchomienie mostka Apple TV i serwera API w tle
PORT=8080
if [ -f "./app/tvdecoder_server.py" ] && ! pgrep -f "tvdecoder_server.py" >/dev/null 2>&1; then
    python3 "./app/tvdecoder_server.py" "$PORT" &
fi
if [ -f "./app/apple_tv_bridge.py" ] && ! pgrep -f "apple_tv_bridge.py" >/dev/null 2>&1; then
    python3 "./app/apple_tv_bridge.py" &
fi

SERVER_URL="http://127.0.0.1:${PORT}/"

# 3. Oczekiwanie na gotowość serwera
echo "[WPE DRM] Oczekiwanie na gotowość serwera: $SERVER_URL..."
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL" 2>/dev/null | grep -q "200\|404"; then
        break
    fi
    sleep 0.1
done

# 4. Sprawdzenie launchera Cog (WPE WebKit)
if ! command -v cog >/dev/null 2>&1; then
    echo "❌ Nie znaleziono odtwarzacza Cog (WPE WebKit)!"
    echo "👉 Zainstaluj go poleceniem: sudo apt install cog libwpewebkit-1.1-0"
    exit 1
fi

echo "[WPE DRM] Uruchamianie interfejsu TV bezpośrednio na wyjściu HDMI (KMS/DRM)..."

# Próba uruchomienia z natywną platformą DRM (KMS/EGL), z fallbackiem na domyślną
if cog --help 2>&1 | grep -q "platform.*drm"; then
    exec cog --platform=drm "$SERVER_URL"
else
    exec cog "$SERVER_URL"
fi
