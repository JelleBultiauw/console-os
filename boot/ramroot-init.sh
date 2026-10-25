# Sourced by the original initramfs before mounting the system images.
# A temporary compatibility test for the 8 GB MacBookPro9,2; userdata stays on USB.
console_ramroot() {
    case " $cmdline " in *' console.ramroot=1 '*) ;; *) return 0 ;; esac
    memory_kb=0
    while read -r key value unit; do
        [ "$key" = 'MemTotal:' ] && memory_kb="$value" && break
    done < /proc/meminfo
    if [ "$memory_kb" -lt 7340032 ]; then
        echo 'Console D3: onvoldoende RAM; kies de standaard-opstartoptie.'
        return 1
    fi
    mkdir -p /overlay_root/ramroot || return 1
    mount -t tmpfs -o size=4608M tmpfs /overlay_root/ramroot || return 1
    for image in batocera rufomaculata; do
        case "$image" in
            batocera) expected_crc=95e3690b ;;
            rufomaculata) expected_crc=9bc8f146 ;;
        esac
        verified=no
        for attempt in 1 2; do
            echo "Console D3: $image naar RAM kopieren ($attempt/2)..."
            if /bin/cp "/boot_root/boot/$image" "/overlay_root/ramroot/$image"; then
                # CRC detects accidental transfer errors. The source images have
                # separately been verified against their full SHA-256 on macOS.
                actual_crc=$(/bin/crc32 "/overlay_root/ramroot/$image") || actual_crc=failed
                set -- $actual_crc
                if [ "${1:-failed}" = "$expected_crc" ]; then
                    verified=yes
                    echo "Console D3: $image controle geslaagd."
                    break
                fi
            fi
            echo 'Console D3: leescontrole mislukt; kopie wordt opnieuw geprobeerd.'
            rm -f "/overlay_root/ramroot/$image"
        done
        if [ "$verified" != yes ]; then
            echo 'Console D3: herhaalde leesfout. Kies standaard-opstart of controleer USB/RAM.'
            return 1
        fi
    done
    printf 'Console D3: beide systeemimages in RAM; CRC32 geverifieerd.\n' > /overlay_root/ramroot/verified.txt
    BASEIMAGE=/overlay_root/ramroot
}
