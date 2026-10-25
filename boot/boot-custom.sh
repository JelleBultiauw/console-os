#!/bin/bash
# Diagnose vanaf S00, dus ook als /userdata nog niet beschikbaar is.
[ "$1" = "start" ] || exit 0
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
/bin/bash /boot/console-os/trace-stage.sh '$stage' before || true
'$ORIGINALS/$stage' "\$@"
result=\$?
/bin/bash /boot/console-os/trace-stage.sh '$stage' "after:\$result" || true
exit \$result
EOF
    chmod +x "$script"
done
exit 0
