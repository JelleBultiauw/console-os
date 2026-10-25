#!/bin/bash
# Batocera voert dit uit nadat de USB-gebruikerspartitie beschikbaar is.
[ "$1" = "start" ] || exit 0
STATE=/userdata/system/console-os
mkdir -p "$STATE"
PYTHON=$(command -v python3 || command -v python) || exit 0
# Het profiel is alleen lokaal in ext4 aanwezig en zit nooit in het updatepakket.
timeout 30 "$PYTHON" /boot/console-os/import-wifi.py >> "$STATE/boot.log" 2>&1 || true
# Een mislukte extra laag mag het bestaande gamemenu nooit blokkeren.
timeout 25 "$PYTHON" /boot/console-os/runtime.py boot >> "$STATE/boot.log" 2>&1 || true
# De meting loopt op de achtergrond zodat de interface direct kan opstarten.
(/bin/bash /boot/console-os/linux-report.sh >> "$STATE/boot.log" 2>&1) &
exit 0
