#!/bin/bash
# Kleine lokale snapshots op FAT, zonder afhankelijkheid van /userdata of Python.
STAGE="$1"
POSITION="$2"
OUT=/boot/CONSOLE-RAPPORT
mount -o remount,rw /boot 2>/dev/null || exit 0
mkdir -p "$OUT" || exit 0
printf '%s %s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$STAGE" "$POSITION" >> "$OUT/opstartfasen.txt"
{
    echo 'CONSOLE OS - OPSTART- EN OPSLAGDIAGNOSE D2'
    printf 'Laatste fase: %s %s\n' "$STAGE" "$POSITION"
    printf 'Model: '; cat /sys/class/dmi/id/product_name 2>/dev/null
    printf 'Kernel: '; uname -r
    echo 'Kernel-opstartopties:'; cat /proc/cmdline
    echo 'Opslaginstelling:'; grep -E '^(sharedevice|autoresize|sharewait)=' /boot/batocera-boot.conf
    echo 'Partities:'; cat /proc/partitions
    echo 'Mounts:'; cat /proc/mounts
    echo 'Beeldschermconnectoren:'
    for connector in /sys/class/drm/card*-*/status; do
        [ -f "$connector" ] || continue
        printf '%s: ' "$connector"; cat "$connector"
    done
    echo 'Actief menu:'; pidof emulationstation 2>/dev/null || true
} > "$OUT/opstartstatus.txt"
dmesg | tail -250 > "$OUT/kernel-laatste.txt"
[ -f /var/log/messages ] && tail -400 /var/log/messages > "$OUT/systeemmeldingen.txt"
for log in /run/console-stage-*.log; do
    [ -f "$log" ] && cp "$log" "$OUT/$(basename "$log")"
done
[ -f /var/run/boot.log ] && cp /var/run/boot.log "$OUT/init-volgorde.txt"
[ -f /tmp/resize.log ] && cp /tmp/resize.log "$OUT/partitievergroting.txt"
[ -f /var/log/Xorg.0.log ] && cp /var/log/Xorg.0.log "$OUT/Xorg.0.log"
[ -f /userdata/system/configs/emulationstation/es_log.txt ] && cp /userdata/system/configs/emulationstation/es_log.txt "$OUT/menu.log"
for log in /userdata/system/logs/es_launch_stdout.log /userdata/system/logs/es_launch_stderr.log; do
    [ -f "$log" ] && cp "$log" "$OUT/$(basename "$log")"
done
sync
mount -o remount,ro /boot 2>/dev/null || true
exit 0
