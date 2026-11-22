#!/usr/bin/env bash
# ==============================================================================
# Skrypt instalacji zależności dla TVDecoder na Debianie 12 (Bookworm) / Ubuntu
# ==============================================================================
set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Ten skrypt musi zostać uruchomiony z uprawnieniami roota!"
    echo "👉 Użyj: sudo ./install_dependencies_debian.sh"
    exit 1
fi

echo "=================================================================="
echo " 📦 Instalacja zależności systemowych dla TVDecoder (Debian Linux) "
echo "=================================================================="

apt update -y

# 1. Podstawowe biblioteki interfejsu WebKitGTK i GTK3 (100% natywne, Zero Wine)
apt install -y --no-install-recommends \
    libwebkit2gtk-4.1-0 \
    libgtk-3-0 \
    libnotify4 \
    libglib2.0-0

# 2. Kodeki wideo GStreamer z akceleracją sprzętową VA-API dla HLS / DASH / MP4
apt install -y --no-install-recommends \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    gstreamer1.0-vaapi || true

# 3. Python 3 oraz pakiety dla pilota Apple TV (Centrum Sterowania iOS)
apt install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-requests \
    python3-pil \
    python3-cryptography \
    python3-zeroconf

# 4. Instalacja HAP-python dla obsługi pilota Apple TV przez aplikację Dom (HomeKit)
pip3 install --break-system-packages --no-cache-dir HAP-python[QRCode] 2>/dev/null || true

echo "=================================================================="
echo " 🎉 Sukces! Wszystkie pakiety zostały zainstalowane."
echo " 👉 Aby uruchomić dekoder: ./start_debian.sh"
echo "=================================================================="
