#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Oficjalny YouTube Smart TV (Cobalt / Leanback)
# ==============================================================================

# 1. User Agent telewizora Smart TV (Tizen 6.0), aby YouTube serwował interfejs TV
TV_USER_AGENT="Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.93 TV Safari/537.36"

# 2. Katalog profilu (zapamiętuje logowanie Google, historię i sparowane smartfony)
USER_DATA_DIR="/home/tvuser/.config/youtube_tv"
mkdir -p "$USER_DATA_DIR"

# 3. Uruchomienie Chromium w trybie Kiosk Smart TV z akceleracją GPU
exec chromium \
    --kiosk \
    --app="https://www.youtube.com/tv" \
    --user-agent="$TV_USER_AGENT" \
    --user-data-dir="$USER_DATA_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-translate \
    --disable-infobars \
    --disable-features=Translate \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --enable-gpu-rasterization \
    --enable-zero-copy \
    --ignore-gpu-blocklist \
    --check-for-update-interval=31536000
