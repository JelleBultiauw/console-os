#!/bin/bash
# Alleen de gegevenspartitie naast de actieve bootpartitie gebruiken.
# Geen formattering of partitie-aanpassing; herstel alleen een tmpfs-fallback.
set -u
TYPE=$(awk '$2 == "/userdata" { print $3 }' /proc/mounts | tail -1)
echo "Console opslagcontrole: /userdata type=$TYPE"
case "$TYPE" in tmpfs|ramfs) ;; *) exit 0 ;; esac
MODE=$(sed -n 's/^sharedevice=//p' /boot/batocera-boot.conf | head -1)
[ "$MODE" = 'INTERNAL' ] || { echo 'Andere opslagkeuze ingesteld; geen automatische override.'; exit 0; }
BOOTPART=$(awk '$2 == "/boot" { print $1 }' /proc/mounts | head -1)
case "$BOOTPART" in
    /dev/sd[a-z]1|/dev/mmcblk[0-9]p1|/dev/nvme[0-9]n[0-9]p1) DATA="${BOOTPART%1}2" ;;
    *) echo 'Onbekende bootpartitie; geen herstel uitgevoerd.'; exit 1 ;;
esac
[ -b "$DATA" ] || { echo "Gegevenspartitie ontbreekt: $DATA"; exit 1; }
echo "Expliciete ext4-herstelpoging vanaf bootdrive: $DATA"
modprobe ext4 2>&1 || true
blkid -p "$DATA" 2>&1 || true
umount /userdata || exit 1
if mount -t ext4 -o noatime "$DATA" /userdata; then
    echo 'Gegevenspartitie is nu blijvend aangekoppeld.'
    touch /userdata/.console-persistence-check
    exit 0
fi
echo 'Blijvende opslag nog niet beschikbaar; herstelmelding wordt bewaard.'
mount -t tmpfs -o size=768M tmpfs /userdata
exit 1
