#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Automatyczny skrypt budowania bootowalnego hybrydowego ISO
# Baza: Debian 12 (Bookworm) Minimal + 100% Natywny Linux Kiosk Appliance (Zero Wine)
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Ten skrypt musi zostać uruchomiony z uprawnieniami roota (sudo)!"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="/tmp/tvdecoder_build"
CHROOT_DIR="$WORK_DIR/chroot"
ISO_DIR="$WORK_DIR/iso"
OUTPUT_ISO="$PROJECT_ROOT/TVDecoderOS.iso"

echo "================================================================================"
echo " 🚀 Rozpoczynanie budowania obrazu TVDecoder OS (Hybrid Live/Install ISO)       "
echo "================================================================================"

# 1. Sprawdzanie i instalacja wymaganych narzędzi na hoście
echo "⏳ [1/7] Weryfikacja narzędzi budowania na hoście..."
apt-get update -y
apt-get install -y debootstrap squashfs-tools xorriso isolinux syslinux-common syslinux-efi grub-pc-bin grub-efi-amd64-bin mtools rsync curl

# 2. Czyszczenie katalogu roboczego
rm -rf "$WORK_DIR"
mkdir -p "$CHROOT_DIR" "$ISO_DIR/live" "$ISO_DIR/boot/grub" "$ISO_DIR/isolinux"

# 3. Bootstrap minimalnego Debiana 12 (Bookworm)
echo "⏳ [2/7] Pobieranie minimalnego systemu bazowego (Debian 12 Bookworm)..."
debootstrap --arch=amd64 bookworm "$CHROOT_DIR" http://deb.debian.org/debian/

# 4. Konfiguracja repozytoriów, jądra i pakietów wewnątrz chroota
echo "⏳ [3/7] Konfiguracja środowiska, sterowników GPU/Audio i natywnego TVDecoder..."

cat <<EOF > "$CHROOT_DIR/etc/apt/sources.list"
deb http://deb.debian.org/debian/ bookworm main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian/ bookworm-updates main contrib non-free non-free-firmware
EOF

cat <<'EOF' > "$CHROOT_DIR/tmp/setup.sh"
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update -y

# Jądro Linux i moduły Live
apt-get install -y --no-install-recommends \
    linux-image-amd64 live-boot live-config systemd-sysv

# Sterowniki GPU, sprzętu i Firmware (pełna akceleracja sprzętowa VA-API/Vulkan/OpenGL)
apt-get install -y --no-install-recommends \
    firmware-linux-free firmware-misc-nonfree xserver-xorg-video-all \
    mesa-vulkan-drivers mesa-va-drivers libgl1-mesa-dri vainfo

# Serwer graficzny X11 + lekki menedżer okien Openbox (dla skrótów pilota)
apt-get install -y --no-install-recommends \
    xserver-xorg-core xinit openbox unclutter xterm x11-xserver-utils

# Natywny silnik programu GUI (PyQt5) oraz natywny odtwarzacz wideo z akceleracją sprzętową (mpv) - ZERO HTML
apt-get install -y --no-install-recommends \
    python3-pyqt5 mpv libmpv2 fonts-dejavu-core

# Dźwięk (ALSA + PipeWire dla HDMI i optycznego wyjścia)
apt-get install -y --no-install-recommends \
    alsa-utils pipewire wireplumber pipewire-audio-client-libraries libspa-0.2-bluetooth pulseaudio-utils

# Narzędzia sieciowe i instalatora
apt-get install -y --no-install-recommends \
    network-manager wpasupplicant parted dosfstools e2fsprogs rsync dialog sudo ca-certificates curl

# Python 3 + biblioteki mostka Apple TV HomeKit i serwera aplikacji
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-requests python3-qrcode python3-pil python3-cryptography python3-zeroconf

# Instalacja HAP-python dla pilota Apple (iPhone) w Centrum Sterowania
pip3 install --break-system-packages --no-cache-dir HAP-python[QRCode] || true

# Tworzenie dedykowanego użytkownika dekodera 'tvuser'
useradd -m -s /bin/bash -G audio,video,input,render,netdev,sudo tvuser
echo "tvuser:tvuser" | chpasswd
echo "tvuser ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/tvuser

# Czyszczenie pamięci podręcznej pakietów
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/*
EOF

chmod +x "$CHROOT_DIR/tmp/setup.sh"
chroot "$CHROOT_DIR" /tmp/setup.sh
rm -f "$CHROOT_DIR/tmp/setup.sh"

# 5. Kopiowanie aplikacji TVDecoder i konfiguracji
echo "⏳ [4/7] Wdrażanie aplikacji TVDecoder i usługi Kiosk..."
mkdir -p "$CHROOT_DIR/opt/tvdecoder/app" "$CHROOT_DIR/opt/tvdecoder/config" "$CHROOT_DIR/opt/tvdecoder/scripts"
cp -r "$PROJECT_ROOT/app/"* "$CHROOT_DIR/opt/tvdecoder/app/"
cp -r "$PROJECT_ROOT/config/"* "$CHROOT_DIR/opt/tvdecoder/config/"
cp -r "$PROJECT_ROOT/scripts/installer.sh" "$CHROOT_DIR/opt/tvdecoder/scripts/"

chmod +x "$CHROOT_DIR/opt/tvdecoder/config"/*.sh
chmod +x "$CHROOT_DIR/opt/tvdecoder/scripts"/*.sh
chmod +x "$CHROOT_DIR/opt/tvdecoder/app/tvdecoder-linux" 2>/dev/null || true
chmod +x "$CHROOT_DIR/opt/tvdecoder/app"/*.py 2>/dev/null || true

# Instalacja usługi systemd
cp "$PROJECT_ROOT/config/tvdecoder-kiosk.service" "$CHROOT_DIR/etc/systemd/system/"
chroot "$CHROOT_DIR" systemctl enable tvdecoder-kiosk.service NetworkManager.service

# Nadanie uprawnień do plików aplikacji
chroot "$CHROOT_DIR" chown -R tvuser:tvuser /opt/tvdecoder

# Kopiowanie kernela i initrd do struktury ISO
echo "⏳ [5/7] Przygotowywanie jądra i initrd dla nośnika Live..."
VMLINUZ=$(ls -1 "$CHROOT_DIR/boot"/vmlinuz-* | sort -V | tail -n 1)
INITRD=$(ls -1 "$CHROOT_DIR/boot"/initrd.img-* | sort -V | tail -n 1)

cp "$VMLINUZ" "$ISO_DIR/live/vmlinuz"
cp "$INITRD" "$ISO_DIR/live/initrd.img"

# 6. Kompresja systemu plików do SquashFS
echo "⏳ [6/7] Kompresja systemu do filesystem.squashfs..."
mksquashfs "$CHROOT_DIR" "$ISO_DIR/live/filesystem.squashfs" -comp xz -e boot

# 7. Konfiguracja bootloaderów (GRUB UEFI + ISOLINUX BIOS) i tworzenie ISO
echo "⏳ [7/7] Generowanie bootowalnego obrazu hybrydowego ISO..."

# Bootloader GRUB (UEFI)
cp "$PROJECT_ROOT/config/grub.cfg" "$ISO_DIR/boot/grub/grub.cfg"

# Przygotowanie bootowalnego EFI img
dd if=/dev/zero of="$ISO_DIR/boot/grub/efi.img" bs=1M count=10
mkfs.vfat "$ISO_DIR/boot/grub/efi.img"
mkdir -p /mnt/efi_tmp
mount "$ISO_DIR/boot/grub/efi.img" /mnt/efi_tmp
mkdir -p /mnt/efi_tmp/EFI/BOOT
grub-mkstandalone -O x86_64-efi -o /mnt/efi_tmp/EFI/BOOT/BOOTX64.EFI "boot/grub/grub.cfg=$PROJECT_ROOT/config/grub.cfg"
umount /mnt/efi_tmp
rmdir /mnt/efi_tmp

# Bootloader ISOLINUX (BIOS)
cp "$PROJECT_ROOT/config/isolinux.cfg" "$ISO_DIR/isolinux/isolinux.cfg"
ISOLINUX_BIN=$(find /usr/lib -name "isolinux.bin" 2>/dev/null | head -n 1)
if [ -n "$ISOLINUX_BIN" ]; then
    cp "$ISOLINUX_BIN" "$ISO_DIR/isolinux/"
fi
find /usr/lib -path "*/syslinux/modules/bios/*" -exec cp {} "$ISO_DIR/isolinux/" \; 2>/dev/null || true

ISOHDPFX=$(find /usr/lib -name "isohdpfx.bin" 2>/dev/null | head -n 1)
MBR_FLAG=""
if [ -n "$ISOHDPFX" ]; then
    MBR_FLAG="-isohybrid-mbr $ISOHDPFX"
fi

# Generowanie finalnego obrazu ISO za pomocą xorriso (Hybrid MBR/GPT)
xorriso -as mkisofs \
    -iso-level 3 \
    -full-iso9660-filenames \
    -volid "TVDECODER_OS" \
    -eltorito-boot isolinux/isolinux.bin \
    -eltorito-catalog isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    $MBR_FLAG \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot -isohybrid-gpt-basdat \
    -output "$OUTPUT_ISO" \
    "$ISO_DIR"

echo "================================================================================"
echo " 🎉 SUKCES! Bootowalny obraz ISO został wygenerowany:"
echo " 📁 $OUTPUT_ISO"
echo " Możesz go nagrać na pendrive programem Rufus lub Ventoy!"
echo "================================================================================"
