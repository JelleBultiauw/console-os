#!/bin/bash
# Diagnose vanaf S00, dus ook als /userdata nog niet beschikbaar is.
[ "$1" = "start" ] || exit 0
# Een oude RTC mag HTTPS-certificaten niet al bij de eerste netwerkverbinding blokkeren.
# Deze ondergrens is de builddatum; normale netwerktijdsynchronisatie blijft leidend.
if [ "$(date -u +%s)" -lt 1792958650 ]; then
    date -u -s '2026-10-25 20:04:10' || true
fi
ORIGINALS=/run/console-os-original
mkdir -p "$ORIGINALS"
/bin/bash /boot/console-os/trace-stage.sh S00bootcustom start || true
for stage in S02resize S05udev S06audio S06modprobe S08connman S11share S12populateshare S31emulationstation; do
    script="/etc/init.d/$stage"
    [ -f "$script" ] || continue
    [ -f "$ORIGINALS/$stage" ] && continue
    cp -p "$script" "$ORIGINALS/$stage" || continue
    cat > "$script" <<EOF
#!/bin/bash
if [ "\${1:-}" != "start" ]; then
    if [ '$stage' = 'S31emulationstation' ]; then
        /bin/bash /boot/console-os/trace-stage.sh '$stage' stopping || true
    fi
    exec '$ORIGINALS/$stage' "\$@"
fi
/bin/bash /boot/console-os/trace-stage.sh '$stage' before || true
'$ORIGINALS/$stage' "\$@" > '/run/console-stage-$stage.log' 2>&1
result=\$?
if [ '$stage' = 'S11share' ]; then
    /bin/bash /boot/console-os/recover-userdata.sh >> '/run/console-stage-$stage.log' 2>&1 || true
fi
/bin/bash /boot/console-os/trace-stage.sh '$stage' "after:\$result" || true
exit \$result
EOF
    chmod +x "$script"
done
exit 0
