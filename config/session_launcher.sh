#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Główny selektor sesji systemowej
# ==============================================================================

# Upewnienie się, że Plymouth zwolnił konsolę i bufor ramki
if command -v plymouth >/dev/null 2>&1; then
    plymouth quit 2>/dev/null || true
fi
sleep 0.3

# Sprawdzenie środowiska wirtualnego (VMware, VirtualBox, QEMU)
IS_VM=0
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt -q; then
    IS_VM=1
fi

# Tryb domyślny (X11 Appliance Kiosk - pełna kompatybilność z PC i maszynami wirtualnymi)
echo "[SessionLauncher] Uruchamianie trybu X11 Kiosk..."
chmod +x /opt/tvdecoder/config/kiosk.sh
exec /usr/bin/xinit /opt/tvdecoder/config/kiosk.sh -- :0 -nocursor -keeptty -quiet
