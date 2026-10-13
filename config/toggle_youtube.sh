#!/usr/bin/env bash
# Przełącznik TV ⟷ YouTube Smart TV dla pilota
if pgrep -x "chromium" >/dev/null 2>&1; then
    pkill -x "chromium"
else
    /opt/tvdecoder/config/launch_youtube_tv.sh &
fi
