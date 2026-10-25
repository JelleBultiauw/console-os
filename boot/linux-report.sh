#!/bin/bash
# Alleen model-/drivergegevens; geen wifiwachtwoorden, IP- of MAC-adressen.
sleep 25
STATE=/userdata/system/console-os
mkdir -p "$STATE"
REPORT="$STATE/linux-hardware.txt"
{
    echo 'CONSOLE OS - LINUX HARDWARETEST'
    date -u
    echo
    printf 'Model: '; cat /sys/class/dmi/id/product_name 2>/dev/null
    printf 'Kernel: '; uname -r
    echo
    echo 'PCI-HARDWARE EN DRIVERS'
    lspci -nnk 2>/dev/null
    echo
    echo 'USB-HARDWARE'
    lsusb 2>/dev/null
    echo
    echo 'WIFI-INTERFACES'
    for d in /sys/class/net/*; do
        [ -d "$d/wireless" ] || continue
        printf '%s driver: ' "$(basename "$d")"
        basename "$(readlink -f "$d/device/driver")"
    done
    echo
    echo 'BLUETOOTH-HARDWARE'
    for d in /sys/class/bluetooth/hci*; do
        [ -e "$d" ] && basename "$d"
    done
    echo
    echo 'GELUIDSKAARTEN'
    aplay -l 2>/dev/null
    echo
    echo 'INVOERAPPARATEN'
    sed -n '/^N: Name=/p; /^H: Handlers=/p' /proc/bus/input/devices 2>/dev/null
    echo
    echo 'WIFI-HARDWAREMOGELIJKHEDEN (GEEN BEWIJS VOOR GAMEPAD-COMPATIBILITEIT)'
    iw list 2>/dev/null
    echo
    echo 'EIGEN UPDATESTATUS'
    cat "$STATE/status.json" 2>/dev/null
} > "$REPORT"
# Maak het rapport leesbaar op macOS via de FAT-bootpartitie.
if mount -o remount,rw /boot; then
    mkdir -p /boot/CONSOLE-RAPPORT
    cp "$REPORT" /boot/CONSOLE-RAPPORT/linux-hardware.txt
    cp "$STATE/status.json" /boot/CONSOLE-RAPPORT/updatestatus.json 2>/dev/null || true
    sync
    mount -o remount,ro /boot || true
fi
