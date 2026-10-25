#!/usr/bin/env python3
"""Write and verify one explicitly identified external USB disk. Requires OS elevation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time


def disk_info(device):
    return plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', device]))


def validate_target(disk, expected_size, expected_uuid):
    if not re.fullmatch(r'/dev/disk[0-9]+', disk):
        raise ValueError('Alleen een hele, expliciet opgegeven disk is toegestaan.')
    info = disk_info(disk)
    if info.get('Internal') is not False or info.get('BusProtocol') != 'USB' or info.get('VirtualOrPhysical') != 'Physical':
        raise ValueError('Dit is geen externe fysieke USB-schijf.')
    if info.get('TotalSize') != expected_size or info.get('Writable') is not True:
        raise ValueError('Afmeting of schrijftoegang van doel komt niet overeen.')
    partition = disk_info(disk + 's1')
    if partition.get('VolumeUUID') != expected_uuid:
        raise ValueError('Dit is niet dezelfde diagnose-stick. Er wordt niets geschreven.')


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--disk', required=True)
    parser.add_argument('--expected-size', required=True, type=int)
    parser.add_argument('--expected-volume-uuid', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('macOS-beheerdersrechten zijn nodig voor het schrijven naar USB.')
    if not re.fullmatch(r'[a-f0-9]{64}', args.sha256):
        raise ValueError('Ongeldige image-checksum.')
    log = Path(args.log).open('w', encoding='utf-8', buffering=1)
    def report(state, **fields):
        line = json.dumps(dict(state=state, **fields))
        log.write(line + '\n')
        print(line, flush=True)
    report('checking')
    image = Path(args.image).resolve(strict=True)
    if image.stat().st_size >= args.expected_size:
        raise ValueError('Image is groter dan de stick.')
    validate_target(args.disk, args.expected_size, args.expected_volume_uuid)
    if digest_file(image) != args.sha256:
        raise ValueError('De image is gewijzigd. Er wordt niets geschreven.')
    # Controleer de fysieke identiteit opnieuw vlak voor de eerste schrijfactie.
    validate_target(args.disk, args.expected_size, args.expected_volume_uuid)
    subprocess.run(['/usr/sbin/diskutil', 'unmountDisk', args.disk], check=True)
    raw = args.disk.replace('/dev/disk', '/dev/rdisk', 1)
    total = image.stat().st_size
    written, last = 0, 0
    started = time.monotonic()
    with image.open('rb') as source, open(raw, 'r+b', buffering=0) as target:
        while True:
            block = source.read(4 * 1024 * 1024)
            if not block:
                break
            remaining = memoryview(block)
            while remaining:
                count = target.write(remaining)
                if not count:
                    raise OSError('USB-schrijfoperatie stopte onverwacht.')
                remaining = remaining[count:]
            written += len(block)
            if time.monotonic() - last >= 5 or written == total:
                report('writing', bytes=written, total=total, percent=round(written / total * 100, 1), elapsed=round(time.monotonic() - started))
                last = time.monotonic()
        try:
            os.fsync(target.fileno())
        except OSError:
            pass
        subprocess.run(['/bin/sync'], check=True)
        # Houd dezelfde raw device-handle open tijdens verificatie. Sluiten en
        # opnieuw openen geeft Disk Arbitration gelegenheid om FAT te mounten
        # en bijvoorbeeld Spotlight-bestanden toe te voegen voor de vergelijking.
        target.seek(0)
        read, last = 0, 0
        digest = hashlib.sha256()
        while read < total:
            block = target.read(min(4 * 1024 * 1024, total - read))
            if not block:
                raise OSError('USB kon niet volledig teruggelezen worden.')
            digest.update(block)
            read += len(block)
            if time.monotonic() - last >= 5 or read == total:
                report('verifying', bytes=read, total=total, percent=round(read / total * 100, 1))
                last = time.monotonic()
    if digest.hexdigest() != args.sha256:
        report('verification-failed')
        raise OSError('Teruggelezen USB-inhoud wijkt af van de image.')
    subprocess.run(['/usr/sbin/diskutil', 'eject', args.disk], check=True)
    report('complete', sha256=digest.hexdigest(), bytes=total)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('FOUT: ' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
