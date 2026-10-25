#!/usr/bin/env python3
"""Create the small GitHub update asset, never the underlying third-party OS image."""
from pathlib import Path
import hashlib
import json
import tarfile

def payload_files(payload):
    for path in sorted(payload.rglob('*')):
        if '__pycache__' in path.parts:
            continue
        if path.is_symlink():
            raise ValueError('Symlinks zijn niet toegestaan in een release.')
        if not path.is_file():
            continue
        relative = path.relative_to(payload)
        if any(p in ('private', '.private', 'secrets', '.secrets') for p in relative.parts) or '.local.' in relative.name or relative.name.startswith('.env'):
            raise ValueError('Lokaal of geheim bestand geweigerd in release.')
        allowed = relative.as_posix() in ('manifest.json', 'runtime.py', 'README.txt')
        allowed = allowed or (relative.parts[0] == 'theme' and path.suffix.lower() in ('.xml', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ttf', '.otf', '.wav', '.ogg'))
        if not allowed:
            raise ValueError('Niet-toegestaan bestand in release.')
        yield path


def build(root):
    payload = root / 'payload'
    version = json.loads((payload / 'manifest.json').read_text())['version']
    paths = list(payload_files(payload))
    output = root / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / 'console-os-update.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in paths:
            info = bundle.gettarinfo(str(path), arcname=path.relative_to(payload).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            with path.open('rb') as source:
                bundle.addfile(info, source)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
    print('v' + version, archive, digest)


if __name__ == '__main__':
    build(Path(__file__).resolve().parent)
