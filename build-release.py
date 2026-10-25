#!/usr/bin/env python3
"""Create the small GitHub update asset, never the underlying third-party OS image."""
from pathlib import Path
import hashlib
import json
import tarfile

root = Path(__file__).resolve().parent
payload = root / 'payload'
version = json.loads((payload / 'manifest.json').read_text())['version']
output = root / 'dist'
output.mkdir(exist_ok=True)
archive = output / 'console-os-update.tar.gz'
with tarfile.open(archive, 'w:gz') as bundle:
    for path in sorted(payload.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            info = bundle.gettarinfo(str(path), arcname=path.relative_to(payload).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            with path.open('rb') as source:
                bundle.addfile(info, source)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n')
print('v' + version, archive, digest)
