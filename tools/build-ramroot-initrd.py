#!/usr/bin/env python3
"""Patch only init in Batocera 43.1's gzip/newc initramfs, preserving all other entries."""
import argparse
import gzip
import hashlib
from pathlib import Path

SOURCE_SHA256 = 'c464e1bf59d3bad76c7eb172370fcc350285878608a677b857cb9922201b5fa9'


def entries(raw):
    pos = 0
    while pos + 110 <= len(raw):
        header = raw[pos:pos + 110]
        if header[:6] != b'070701':
            raise ValueError('Expected a newc archive.')
        size = int(header[54:62], 16)
        namesize = int(header[94:102], 16)
        name_end = pos + 110 + namesize
        name = raw[pos + 110:name_end]
        if not name.endswith(b'\0'):
            raise ValueError('Invalid archive name.')
        start = (name_end + 3) & ~3
        end = start + size
        if end > len(raw):
            raise ValueError('Truncated archive.')
        yield name[:-1].decode(), header, raw[start:end]
        pos = (end + 3) & ~3
        if name == b'TRAILER!!!\0':
            return
    raise ValueError('Missing archive trailer.')


def patch_init(original, fragment, test_shell=False):
    text = original.decode()
    anchor = '    # mount the squashfs\n    mount /boot_root/boot/batocera /overlay_root/base || return 1'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected Batocera init layout.')
    text = text.replace('do_mount() {', fragment + '\n\ndo_mount() {', 1)
    text = text.replace(anchor, '    BASEIMAGE=/boot_root/boot\n    console_ramroot || return 1\n\n    # mount the squashfs\n    mount "$BASEIMAGE/batocera" /overlay_root/base || return 1', 1)
    text = text.replace('mount /boot_root/boot/rufomaculata /overlay_root/base2', 'mount "$BASEIMAGE/rufomaculata" /overlay_root/base2')
    text = text.replace('mount /boot_root/boot/batocera /new_root', 'mount "$BASEIMAGE/batocera" /new_root')
    if test_shell:
        text = text.replace('exec switch_root /new_root /sbin/init', 'exec switch_root /new_root /bin/sh')
    return text.encode()


def build(source, fragment, test_shell=False):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unexpected source initramfs; refusing to patch.')
    output = bytearray()
    changed = 0
    for name, header, data in entries(gzip.decompress(source)):
        if name == 'init':
            data = patch_init(data, fragment, test_shell)
            changed += 1
            header = header[:54] + ('%08x' % len(data)).encode() + header[62:]
        output.extend(header)
        output.extend(name.encode() + b'\0')
        output.extend(b'\0' * (-len(output) % 4))
        output.extend(data)
        output.extend(b'\0' * (-len(output) % 4))
    if changed != 1:
        raise ValueError('Expected exactly one init entry.')
    output.extend(b'\0' * (-len(output) % 512))
    return gzip.compress(bytes(output), mtime=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--test-shell', action='store_true', help='Local VM verification only; do not deploy this image.')
    args = parser.parse_args()
    fragment = (Path(__file__).resolve().parents[1] / 'boot/ramroot-init.sh').read_text()
    args.output.write_bytes(build(args.source.read_bytes(), fragment, args.test_shell))
    print('Initramfs generated; only init was patched.')
