#!/usr/bin/env bash
# ==============================================================================
# Aurora OS - Główny selektor sesji systemowej
# ==============================================================================
plymouth --quit 2>/dev/null || true

# Sprawdzenie środowiska wirtualnego (VMware, VirtualBox, QEMU)
IS_VM=0
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt -q; then
    IS_VM=1
fi

# Jeśli użytkownik wybrał WPE DRM i NIE jesteśmy w maszynie wirtualnej:
if grep -q "ui_mode=wpe" /proc/cmdline && [ "$IS_VM" -eq 0 ] && [ -f "/opt/tvdecoder/scripts/start_wpe_drm.sh" ]; then
    echo "[SessionLauncher] Uruchamianie trybu WPE Direct DRM (Opcja C)..."
    chmod +x /opt/tvdecoder/scripts/start_wpe_drm.sh
    exec /opt/tvdecoder/scripts/start_wpe_drm.sh
fi

# Jeśli użytkownik wybrał Wayland i NIE jesteśmy w maszynie wirtualnej:
if grep -q "ui_mode=wayland" /proc/cmdline && [ "$IS_VM" -eq 0 ] && [ -f "/opt/tvdecoder/scripts/start_wayland.sh" ]; then
    echo "[SessionLauncher] Uruchamianie trybu Wayland Kiosk Cage (Opcja B)..."
    chmod +x /opt/tvdecoder/scripts/start_wayland.sh
    exec /opt/tvdecoder/scripts/start_wayland.sh
fi

# Tryb domyślny oraz dla maszyn wirtualnych (X11 Appliance Kiosk - 100% gwarancji działania)
echo "[SessionLauncher] Uruchamianie trybu X11 Kiosk..."
chmod +x /opt/tvdecoder/config/kiosk.sh
exec /usr/bin/xinit /opt/tvdecoder/config/kiosk.sh -- :0 vt1 -nocursor -keeptty -quiet

