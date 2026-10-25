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
    echo
    echo 'OPSLAG EN NETWERK'
    findmnt -n -o SOURCE,FSTYPE,SIZE,AVAIL /userdata 2>/dev/null
    if ip route show default 2>/dev/null | grep -q .; then
        echo 'Standaard netwerkroute: aanwezig'
    else
        echo 'Standaard netwerkroute: ontbreekt'
    fi
    if [ -e /sys/class/net/wlan0/operstate ]; then
        printf 'Wifi-interface: '; cat /sys/class/net/wlan0/operstate
    fi
    echo 'Lokaal wifi-importresultaat (geen netwerknaam of wachtwoord):'
    cat "$STATE/wifi-import-status.json" 2>/dev/null
    echo 'Draadloze blokkeringen:'
    rfkill list 2>/dev/null
    echo 'Klok:'; date -u
} > "$REPORT"
# Maak het rapport leesbaar op macOS via de FAT-bootpartitie.
if mount -o remount,rw /boot; then
    mkdir -p /boot/CONSOLE-RAPPORT
    cp "$REPORT" /boot/CONSOLE-RAPPORT/linux-hardware.txt
    cp "$STATE/status.json" /boot/CONSOLE-RAPPORT/updatestatus.json 2>/dev/null || true
    [ -f /var/log/Xorg.0.log ] && cp /var/log/Xorg.0.log /boot/CONSOLE-RAPPORT/Xorg.0.log
    [ -f /userdata/system/configs/emulationstation/es_log.txt ] && cp /userdata/system/configs/emulationstation/es_log.txt /boot/CONSOLE-RAPPORT/menu.log
    [ -f /var/run/boot.log ] && cp /var/run/boot.log /boot/CONSOLE-RAPPORT/init-volgorde.txt
    [ -f /tmp/resize.log ] && cp /tmp/resize.log /boot/CONSOLE-RAPPORT/partitievergroting.txt
    [ -f /var/log/messages ] && tail -400 /var/log/messages > /boot/CONSOLE-RAPPORT/systeemmeldingen.txt
    sync
    mount -o remount,ro /boot || true
fi
