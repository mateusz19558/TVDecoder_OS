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

# Konfiguracja nazwy hosta TVDecoder OS i stabilnego DNS
echo "tvdecoder" > "$CHROOT_DIR/etc/hostname"
cat <<EOF > "$CHROOT_DIR/etc/hosts"
127.0.0.1 localhost tvdecoder
::1       localhost ip6-localhost ip6-loopback
EOF

mkdir -p "$CHROOT_DIR/etc"
cat <<EOF > "$CHROOT_DIR/etc/resolv.conf"
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF

mkdir -p "$CHROOT_DIR/etc/apt/apt.conf.d"
cat <<EOF > "$CHROOT_DIR/etc/apt/apt.conf.d/99retries"
Acquire::Retries "5";
Acquire::http::Timeout "45";
Acquire::https::Timeout "45";
EOF

cleanup_chroot() {
    umount -lf "$CHROOT_DIR/dev/pts" 2>/dev/null || true
    umount -lf "$CHROOT_DIR/dev" 2>/dev/null || true
    umount -lf "$CHROOT_DIR/proc" 2>/dev/null || true
    umount -lf "$CHROOT_DIR/sys" 2>/dev/null || true
}
trap cleanup_chroot EXIT

cat <<'EOF' > "$CHROOT_DIR/tmp/setup.sh"
#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

ensure_dns() {
    rm -f /etc/resolv.conf
    cat <<'DNS' > /etc/resolv.conf
nameserver 8.8.8.8
nameserver 1.1.1.1
DNS
}

ensure_dns
apt-get update -y || (sleep 3 && ensure_dns && apt-get update -y)

apt_install() {
    ensure_dns
    apt-get install -y --fix-missing --no-install-recommends "$@" || (
        echo "⚠️ Ponawianie pobierania pakietów..."
        sleep 3
        ensure_dns
        apt-get update -y --fix-missing
        apt-get install -y --fix-missing --no-install-recommends "$@"
    )
}

# Instalacja wszystkich wymaganych pakietów w jednej transakcji (zapobiega konfliktom i utracie DNS w trakcie)
apt_install \
    linux-image-amd64 live-boot live-config systemd-sysv \
    firmware-linux-free firmware-misc-nonfree firmware-amd-graphics xserver-xorg-video-all xserver-xorg-video-vmware xserver-xorg-video-fbdev xserver-xorg-video-vesa \
    mesa-vulkan-drivers mesa-va-drivers libgl1-mesa-dri vainfo \
    xserver-xorg-core xserver-xorg-legacy xinit openbox unclutter xterm x11-xserver-utils python3-tk feh plymouth plymouth-themes \
    xserver-xorg-input-all xserver-xorg-input-libinput xserver-xorg-input-evdev \
    open-vm-tools open-vm-tools-desktop udev libinput-bin \
    lightdm lightdm-gtk-greeter \
    fonts-dejavu fonts-liberation libnss3 libnspr4 libasound2 libkrb5-3 libssl3 \
    libfontconfig1 libfreetype6 libx11-6 libx11-xcb1 libxrandr2 libxi6 libxcursor1 libgl1 \
    libvlc5 libvlc-dev vlc-plugin-base \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav \
    alsa-utils pipewire wireplumber pipewire-audio-client-libraries libspa-0.2-bluetooth pulseaudio-utils \
    network-manager wpasupplicant systemd-resolved isc-dhcp-client iproute2 net-tools \
    parted dosfstools e2fsprogs rsync dialog sudo ca-certificates curl \
    python3 python3-pip python3-requests python3-qrcode python3-pil python3-cryptography python3-zeroconf

# Konfiguracja uprawnień Xorg dla użytkownika kiosku
mkdir -p /etc/X11
cat <<'XWRAPPER' > /etc/X11/Xwrapper.config
allowed_users=anybody
needs_root_rights=yes
XWRAPPER
chmod u+s /usr/lib/xorg/Xorg.wrap 2>/dev/null || true

# Instalacja HAP-python dla pilota Apple (iPhone) w Centrum Sterowania
ensure_dns
pip3 install --break-system-packages --no-cache-dir HAP-python[QRCode] || true

# Tworzenie dedykowanego użytkownika dekodera 'tvuser' z uprawnieniami autologin
groupadd -r autologin 2>/dev/null || true
useradd -m -s /bin/bash -G audio,video,input,render,netdev,sudo,tty,autologin tvuser
echo "tvuser:tvuser" | chpasswd
echo "tvuser ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/tvuser

# Konfiguracja live-config pod użytkownika tvuser
mkdir -p /etc/live/config.conf.d
cat <<'LIVECONF' > /etc/live/config.conf.d/tvdecoder.conf
LIVE_USERNAME="tvuser"
LIVE_USER_DEFAULT_GROUPS="audio,video,input,render,netdev,sudo,tty,autologin"
LIVECONF

# Czyszczenie pamięci podręcznej pakietów
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/*
EOF

mount --bind /dev "$CHROOT_DIR/dev"
mount --bind /dev/pts "$CHROOT_DIR/dev/pts"
mount -t proc proc "$CHROOT_DIR/proc"
mount -t sysfs sysfs "$CHROOT_DIR/sys"

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
chmod +x "$CHROOT_DIR/opt/tvdecoder/app/AuroraOS" 2>/dev/null || true
chmod +x "$CHROOT_DIR/opt/tvdecoder/app/TVDecoder_Linux" 2>/dev/null || true
chmod +x "$CHROOT_DIR/opt/tvdecoder/app/tvdecoder-linux" 2>/dev/null || true
chmod +x "$CHROOT_DIR/opt/tvdecoder/app"/*.py 2>/dev/null || true

# Rejestracja Aurora OS jako głównej sesji pulpitu (Desktop Session) w LightDM
mkdir -p "$CHROOT_DIR/usr/share/xsessions"
cp "$PROJECT_ROOT/config/aurora.desktop" "$CHROOT_DIR/usr/share/xsessions/"

# Konfiguracja automatycznego logowania do sesji Aurora w LightDM
mkdir -p "$CHROOT_DIR/etc/lightdm/lightdm.conf.d"
cp "$PROJECT_ROOT/config/10-aurora-autologin.conf" "$CHROOT_DIR/etc/lightdm/lightdm.conf.d/"

# Konfiguracja automatycznego DHCP dla połączeń kablowych i VMware
mkdir -p "$CHROOT_DIR/etc/systemd/network"
cat <<'NETCONF' > "$CHROOT_DIR/etc/systemd/network/20-wired.network"
[Match]
Name=en* eth*

[Network]
DHCP=yes
IPv6AcceptRA=yes
NETCONF

mkdir -p "$CHROOT_DIR/etc/NetworkManager"
cat <<'NMCONF' > "$CHROOT_DIR/etc/NetworkManager/NetworkManager.conf"
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true

[device]
wifi.scan-rand-mac-address=no
NMCONF

# Ustawienie domyślnego trybu graficznego oraz włączenie LightDM, NetworkManager, DHCP i VMware Tools
chroot "$CHROOT_DIR" systemctl set-default graphical.target
chroot "$CHROOT_DIR" systemctl enable lightdm.service NetworkManager.service systemd-networkd.service systemd-resolved.service open-vm-tools.service 2>/dev/null || true

# Nadanie uprawnień do plików aplikacji
chroot "$CHROOT_DIR" chown -R tvuser:tvuser /opt/tvdecoder

# Odmontowanie tymczasowych systemów plików chroota przed pakowaniem SquashFS
cleanup_chroot

# Kopiowanie kernela i initrd do struktury ISO
echo "⏳ [5/7] Przygotowywanie jądra i initrd dla nośnika Live..."
VMLINUZ=$(ls -1 "$CHROOT_DIR/boot"/vmlinuz-* 2>/dev/null | sort -V | tail -n 1)
INITRD=$(ls -1 "$CHROOT_DIR/boot"/initrd.img-* 2>/dev/null | sort -V | tail -n 1)

if [ -z "$VMLINUZ" ] || [ ! -f "$VMLINUZ" ]; then
    echo "❌ Błąd: Nie znaleziono pliku jądra w $CHROOT_DIR/boot/vmlinuz-*!"
    exit 1
fi

if [ -z "$INITRD" ] || [ ! -f "$INITRD" ]; then
    echo "❌ Błąd: Nie znaleziono pliku initrd w $CHROOT_DIR/boot/initrd.img-*!"
    exit 1
fi

echo "   Jądro: $VMLINUZ"
echo "   Initrd: $INITRD"
cp -L "$VMLINUZ" "$ISO_DIR/live/vmlinuz"
cp -L "$INITRD" "$ISO_DIR/live/initrd.img"

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
grub-mkstandalone -O x86_64-efi -o /mnt/efi_tmp/EFI/BOOT/BOOTX64.EFI \
    --modules="part_gpt part_msdos fat iso9660 ntfs ext2 normal test linux search search_fs_file search_label efi_gop all_video font gfxterm echo video" \
    "boot/grub/grub.cfg=$PROJECT_ROOT/config/grub.cfg"
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

cp -f "$OUTPUT_ISO" "$PROJECT_ROOT/AuroraOS.iso" 2>/dev/null || true

echo "================================================================================"
echo " 🎉 SUKCES! Bootowalny obraz ISO został wygenerowany:"
echo " 📁 $OUTPUT_ISO oraz $PROJECT_ROOT/AuroraOS.iso"
echo " Możesz go nagrać na pendrive programem Rufus lub Ventoy!"
echo "================================================================================"
