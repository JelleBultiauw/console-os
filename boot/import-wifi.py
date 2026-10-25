#!/usr/bin/env python3
"""Apply a locally provisioned Wi-Fi profile; never log SSID/password values."""
import json
import os
from pathlib import Path
import subprocess

PROFILE = Path('/userdata/system/console-os/wifi.local.json')


def validate_profile(value):
    if not isinstance(value, dict):
        raise ValueError('Ongeldig profiel.')
    for key in ('ssid', 'password'):
        if not isinstance(value.get(key), str) or not value[key] or any(c in value[key] for c in ('\0', '\r', '\n')):
            raise ValueError('Ongeldig profielveld.')
    if len(value['ssid'].encode('utf-8')) > 32 or len(value['password']) > 256:
        raise ValueError('Profielveld te lang.')
    country = value.get('country', 'BE')
    if not isinstance(country, str) or len(country) != 2 or not country.isascii() or not country.isalpha():
        raise ValueError('Ongeldige regio.')
    return value['ssid'], value['password'], country.upper()


def import_profile(profile=PROFILE, runner=None, mounts=None):
    profile = Path(profile)
    if not profile.exists():
        return False
    runner = runner or subprocess.run
    mounts = Path('/proc/mounts').read_text() if mounts is None else mounts
    if any(len(row) >= 3 and row[1] == '/userdata' and row[2] in ('tmpfs', 'ramfs') for row in (line.split() for line in mounts.splitlines())):
        raise RuntimeError('Blijvende opslag ontbreekt; wifi-profiel blijft onaangeroerd.')
    ssid, password, country = validate_profile(json.loads(profile.read_text(encoding='utf-8')))
    result = runner(['/usr/bin/batocera-wifi', 'enable', ssid, password, country], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25, check=False)
    if result.returncode != 0:
        raise RuntimeError('Wifi-instellingen konden niet worden toegepast.')
    # De bestaande Batocera-helper schrijft/escapet de instellingen en herlaadt ConnMan.
    config = profile.parents[1] / 'batocera.conf'
    if config.exists():
        os.chmod(config, 0o600)
    marker = profile.with_name('wifi-import-status.json')
    marker.write_text(json.dumps({'state': 'configured', 'connection': 'needs-live-check', 'source': 'local-private-profile'}) + '\n')
    os.chmod(marker, 0o600)
    profile.unlink()
    return True


if __name__ == '__main__':
    try:
        changed = import_profile()
        if changed:
            print('Lokaal wifi-profiel toegepast; verbinding wordt afzonderlijk gecontroleerd.')
    except Exception:
        # Exceptiontekst kan gegevens uit een onjuist profiel bevatten: niet afdrukken.
        print('Wifi-profiel nog niet toegepast; het lokale profiel is bewaard voor een volgende start.')
        raise SystemExit(1)
