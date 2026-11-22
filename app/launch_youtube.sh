#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Dedykowany Launcher YouTube Smart TV (Leanback Interface)
# ==============================================================================

URL="${1:-https://www.youtube.com/tv}"
UA="Mozilla/5.0 (SMART-TV; Linux; Tizen 7.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.125 TV Safari/537.36"

# Zamknięcie ewentualnej poprzedniej instancji
pkill -f "chromium.*youtube.com" 2>/dev/null || true
sleep 0.2

if command -v chromium >/dev/null 2>&1; then
    exec chromium \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --autoplay-policy=no-user-gesture-required \
        --user-agent="$UA" \
        "$URL"
elif command -v chromium-browser >/dev/null 2>&1; then
    exec chromium-browser \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --no-first-run \
        --autoplay-policy=no-user-gesture-required \
        --user-agent="$UA" \
        "$URL"
elif command -v firefox >/dev/null 2>&1; then
    exec firefox --kiosk "$URL"
elif command -v mpv >/dev/null 2>&1; then
    exec mpv --fs "https://www.youtube.com"
fi
