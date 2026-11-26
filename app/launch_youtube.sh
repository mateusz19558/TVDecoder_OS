#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Dedykowany Launcher YouTube Smart TV (Szybki start Leanback TV)
# ==============================================================================

URL="${1:-https://www.youtube.com/tv}"
UA="Mozilla/5.0 (PS4; Leanback Shell) Gecko/20100101 Firefox/65.0 LeanbackShell/01.00.01.75 Sony PS4/ (PS4, , no, CH)"
PROFILE_DIR="/home/tvuser/.config/aurora_yt_profile"
CACHE_DIR="/tmp/aurora_yt_cache"
EXT_DIR="/opt/tvdecoder/config/yt_bridge_ext"

mkdir -p "$PROFILE_DIR" "$CACHE_DIR" 2>/dev/null || true

# Jeśli Chromium z YT już działa w tle, po prostu przywróć jego okno zamiast uruchamiać od zera
if pgrep -f "aurora_yt_profile" >/dev/null 2>&1; then
    wmctrl -a "YouTube" 2>/dev/null || true
    exit 0
fi

EXT_ARGS=""
if [ -d "$EXT_DIR" ]; then
    EXT_ARGS="--load-extension=$EXT_DIR"
fi

BIN=""
if command -v chromium >/dev/null 2>&1; then
    BIN="chromium"
elif command -v chromium-browser >/dev/null 2>&1; then
    BIN="chromium-browser"
fi

if [ -n "$BIN" ]; then
    exec "$BIN" \
        --kiosk \
        --no-sandbox \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --no-default-browser-check \
        --disable-background-networking \
        --disable-sync \
        --disable-component-update \
        --disable-features=UserAgentClientHint,Translate,OptimizationHints,MediaRouter \
        --autoplay-policy=no-user-gesture-required \
        --user-data-dir="$PROFILE_DIR" \
        --disk-cache-dir="$CACHE_DIR" \
        $EXT_ARGS \
        --user-agent="$UA" \
        "$URL"
elif command -v firefox >/dev/null 2>&1; then
    exec firefox --kiosk "$URL"
fi
