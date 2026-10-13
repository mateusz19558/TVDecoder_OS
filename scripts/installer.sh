#!/usr/bin/env bash
# ==============================================================================
# TVDecoder OS - Dedykowany Instalator na Dysk
# ==============================================================================

set -e

clear
echo "================================================================================"
echo "                   📺 INSTALATOR SYSTEMU TVDecoder OS 📺                         "
echo "================================================================================"
echo " Ten program zainstaluje TVDecoder OS na wybranym dysku komputera."
echo " Komputer zamieni się w dedykowany dekoder TV uruchamiający się w kilka sekund."
echo "================================================================================"
echo ""

# Lista dostępnych dysków (z wyłączeniem nośnika USB live)
echo "Wykryte dyski w komputerze:"
lsblk -d -p -n -l -o NAME,SIZE,MODEL,TRAN | grep -v "usb" || lsblk -d -p -n -l -o NAME,SIZE,MODEL

echo ""
echo "Podaj nazwę urządzenia, na którym chcesz zainstalować system (np. /dev/sda lub /dev/nvme0n1):"
read -r TARGET_DISK

if [ -z "$TARGET_DISK" ] || [ ! -b "$TARGET_DISK" ]; then
    echo "❌ Błąd: Podano nieprawidłowe urządzenie '$TARGET_DISK'!"
    exit 1
fi

echo ""
echo "⚠️  UWAGA! Wszystkie dane na dysku $TARGET_DISK zostaną CAŁKOWICIE USUNIĘTE!"
read -p "Czy na pewno chcesz kontynuować? Wpisz 'TAK' i naciśnij Enter: " CONFIRM

if [ "$CONFIRM" != "TAK" ]; then
    echo "Instalacja przerwana przez użytkownika."
    exit 0
fi

echo ""
echo "⏳ [1/5] Czyszczenie i partycjonowanie dysku $TARGET_DISK (GPT / UEFI + BIOS)..."
wipefs -a "$TARGET_DISK" || true

# Tworzenie tablicy partycji GPT:
# Partycja 1: EFI System Partition (512MB)
# Partycja 2: TVDecoder System (Reszta dysku)
parted -s "$TARGET_DISK" mklabel gpt
parted -s "$TARGET_DISK" mkpart ESP fat32 1MiB 513MiB
parted -s "$TARGET_DISK" set 1 esp on
parted -s "$TARGET_DISK" mkpart primary ext4 513MiB 100%

# Nazwy partycji w zależności od typu dysku (np. /dev/sda1 vs /dev/nvme0n1p1)
if [[ "$TARGET_DISK" =~ nvme|mmcblk ]]; then
    PART_EFI="${TARGET_DISK}p1"
    PART_ROOT="${TARGET_DISK}p2"
else
    PART_EFI="${TARGET_DISK}1"
    PART_ROOT="${TARGET_DISK}2"
fi

udevadm settle
sleep 1

echo "⏳ [2/5] Formatowanie partycji..."
mkfs.vfat -F32 "$PART_EFI"
mkfs.ext4 -F -L "TVDECODER_OS" "$PART_ROOT"

echo "⏳ [3/5] Kopiowanie plików systemu operacyjnego..."
mkdir -p /mnt/target
mount "$PART_ROOT" /mnt/target
mkdir -p /mnt/target/boot/efi
mount "$PART_EFI" /mnt/target/boot/efi

# Kopiowanie z warstwy Live
if [ -d "/run/live/rootfs/filesystem.squashfs" ] || [ -d "/lib/live/mount/rootfs" ]; then
    rsync -aAXv --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/target/
else
    rsync -aAXv --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/target/
fi

echo "⏳ [4/5] Konfiguracja fstab i bootloadera GRUB..."
UUID_ROOT=$(blkid -s UUID -o value "$PART_ROOT")
UUID_EFI=$(blkid -s UUID -o value "$PART_EFI")

cat <<EOF > /mnt/target/etc/fstab
UUID=$UUID_ROOT / ext4 errors=remount-ro 0 1
UUID=$UUID_EFI /boot/efi vfat umask=0077 0 1
EOF

# Instalacja GRUB dla UEFI
mount --bind /dev /mnt/target/dev
mount --bind /proc /mnt/target/proc
mount --bind /sys /mnt/target/sys

chroot /mnt/target grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=TVDecoder --recheck || true
chroot /mnt/target update-grub

echo "⏳ [5/5] Finalizacja i odmontowywanie..."
umount -R /mnt/target

echo ""
echo "================================================================================"
echo "    🎉 INSTALACJA ZAKOŃCZONA SUKCESEM! 🎉"
echo " Wyjmij pendrive USB i naciśnij Enter, aby zrestartować komputer do TVDecoder OS!"
echo "================================================================================"
read -r
reboot
