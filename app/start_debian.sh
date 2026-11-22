#!/usr/bin/env bash
# ==============================================================================
# Aurora OS • TVDecoder (Natywny Linux Kiosk)
# Zero Wine • 100% Natywny Podsystem Linux / WebKitGTK / Mesa VA-API
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Nadanie praw wykonywania binarce i skryptom
chmod +x ./AuroraOS ./TVDecoder_Linux 2>/dev/null || true
chmod +x ./app/*.py 2>/dev/null || true

# Ścieżka do bibliotek dynamicznych (Photino.Native.so)
export LD_LIBRARY_PATH="$SCRIPT_DIR:$LD_LIBRARY_PATH"

# Optymalizacje sprzętowe dla WebKitGTK i akceleracji GPU Mesa DRI / VA-API
export WEBKIT_FORCE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=0

echo "=================================================================="
echo " 📺 Uruchamianie Aurora OS (Natywna Wersja Linux Debian - Zero Wine) "
echo "=================================================================="

if [ -x "./AuroraOS" ]; then
    exec ./AuroraOS "$@"
else
    exec ./TVDecoder_Linux "$@"
fi
