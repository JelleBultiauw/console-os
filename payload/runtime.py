#!/usr/bin/env python3
"""Console OS user layer. The kernel, emulators, games and saves are never replaced here."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MAX_DOWNLOAD = 32 * 1024 * 1024
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def version_tuple(value):
    value = value.removeprefix('v')
    if not VERSION.fullmatch(value):
        raise ValueError('Alleen stabiele versies met drie versienummers worden ondersteund.')
    return tuple(int(part) for part in value.split('.'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def atomic_link(target, link):
    link = Path(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(link.name + '.new')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def unpack_package(archive, destination, expected_version=None):
    """Only regular files under explicit namespaces; reject path/link escapes."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        if len(members) > 200:
            raise ValueError('Te veel bestanden in update.')
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError('Ongeldig pad in update.')
            if str(path) in names:
                raise ValueError('Dubbel bestand in update.')
            names.add(str(path))
            if not member.isfile():
                raise ValueError('Alleen gewone bestanden zijn toegestaan.')
            if str(path) not in ('manifest.json', 'runtime.py', 'README.txt') and path.parts[0] != 'theme':
                raise ValueError('Niet-toegestaan onderdeel in update.')
            total += member.size
            if total > MAX_DOWNLOAD:
                raise ValueError('Uitgepakte update is te groot.')
        for member in members:
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
    manifest = read_json(destination / 'manifest.json')
    version_tuple(manifest['version'])
    if expected_version and manifest['version'] != expected_version.removeprefix('v'):
        raise ValueError('Versie in pakket komt niet overeen met release.')
    if manifest.get('schema') != 1 or manifest.get('architecture') != 'x86_64' or manifest.get('base') != 'batocera-43.1':
        raise ValueError('Update is niet geschikt voor deze basisversie.')
    ET.parse(destination / 'theme/theme.xml')
    compile((destination / 'runtime.py').read_text(), 'runtime.py', 'exec')
    return manifest


class Console:
    def __init__(self, state='/userdata/system/console-os', boot='/boot/console-os', userdata='/userdata'):
        self.state, self.boot, self.userdata = Path(state), Path(boot), Path(userdata)
        self.state.mkdir(parents=True, exist_ok=True)

    def status(self, state, message, **extra):
        atomic_json(self.state / 'status.json', dict(state=state, message=message, time=time.time(), **extra))
        print(message, flush=True)

    def current_version(self):
        try:
            return read_json(self.state / 'current/manifest.json')['version']
        except (OSError, ValueError, KeyError):
            return '0.0.0'

    def activate(self, release):
        current = self.state / 'current'
        if current.is_symlink():
            old = current.resolve()
            if old != release.resolve():
                atomic_link(old, self.state / 'previous')
        atomic_link(release.resolve(), current)
        atomic_link(current / 'theme', self.userdata / 'themes/console-os')

    def install(self, archive, expected_version=None):
        releases = self.state / 'releases'
        releases.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.staging-', dir=releases) as temporary:
            stage = Path(temporary)
            manifest = unpack_package(archive, stage, expected_version)
            target = releases / manifest['version']
            if target.exists():
                # Released versions are immutable. Never overwrite an existing installation.
                if read_json(target / 'manifest.json') != manifest:
                    raise ValueError('Bestaande versie heeft andere metadata.')
            else:
                os.rename(stage, target)
            self.activate(target)
        return manifest['version']

    def configure_first_boot(self):
        marker = self.state / 'configured-v1'
        if marker.exists():
            return
        path = self.userdata / 'system/configs/emulationstation/es_settings.cfg'
        path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.parse(path) if path.exists() else ET.ElementTree(ET.Element('config'))
        root = tree.getroot()
        for name, value in {'ThemeSet': 'console-os', 'TransitionStyle': 'instant', 'GamelistViewStyle': 'basic'}.items():
            element = next((e for e in root if e.get('name') == name), None)
            if element is None:
                element = ET.SubElement(root, 'string', name=name)
            element.set('value', value)
        temporary = path.with_name(path.name + '.console-new')
        tree.write(temporary, encoding='utf-8', xml_declaration=True)
        os.replace(temporary, path)
        config = self.userdata / 'system/batocera.conf'
        text = config.read_text() if config.exists() else ''
        defaults = {'system.language': 'nl_NL', 'system.timezone': 'Europe/Brussels', 'wifi.enabled': '1', 'splash.screen.sound': '0'}
        for key, value in defaults.items():
            if not re.search(r'^' + re.escape(key) + r'=', text, re.MULTILINE):
                text += '\n' + key + '=' + value
        config.write_text(text + '\n')
        marker.write_text('1\n')

    def request(self, url, limit):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('api.github.com', 'github.com'):
            raise ValueError('Alleen GitHub HTTPS-downloads zijn toegestaan.')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Console-OS/0.1'}
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=5) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Download overschrijdt maximale grootte.')
        return data

    def update(self):
        config = read_json(self.boot / 'config.json')
        repo = config.get('repository', '')
        if not config.get('automatic_updates', True):
            self.status('disabled', 'Automatische updates staan uit.')
            return False
        if not REPOSITORY.fullmatch(repo):
            self.status('unconfigured', 'Er is nog geen GitHub-repository ingesteld.')
            return False
        current = self.current_version()
        try:
            latest = json.loads(self.request('https://api.github.com/repos/' + repo + '/releases/latest', 2 * 1024 * 1024))
            if latest.get('draft') or latest.get('prerelease'):
                raise ValueError('Release is niet stabiel.')
            tag = latest['tag_name']
            rejected = self.state / 'rejected-version'
            if rejected.exists() and rejected.read_text().strip() == tag.removeprefix('v'):
                self.status('held-back', 'Deze versie is eerder teruggedraaid; wacht op een volgende release.', version=current)
                return False
            if version_tuple(tag) <= version_tuple(current):
                self.status('current', 'Geen nieuwere update beschikbaar.', version=current)
                return False
            asset_name = config.get('asset_name', 'console-os-update.tar.gz')
            asset = next(a for a in latest['assets'] if a['name'] == asset_name)
            checksum = next(a for a in latest['assets'] if a['name'] == asset_name + '.sha256')
            prefix = 'https://github.com/' + repo + '/releases/download/' + urllib.parse.quote(tag, safe='') + '/'
            for item in (asset, checksum):
                if not item['browser_download_url'].startswith(prefix):
                    raise ValueError('Download hoort niet bij deze repository/release.')
            if asset.get('size', MAX_DOWNLOAD + 1) > MAX_DOWNLOAD:
                raise ValueError('Updatebestand is te groot.')
            digest = self.request(checksum['browser_download_url'], 1024).decode('ascii').split()[0]
            if not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                raise ValueError('Ongeldige SHA-256-controle.')
            data = self.request(asset['browser_download_url'], MAX_DOWNLOAD)
            if hashlib.sha256(data).hexdigest() != digest.lower():
                raise ValueError('Checksum klopt niet; bestaande versie behouden.')
            with tempfile.TemporaryDirectory(dir=self.state, prefix='.download-') as temporary:
                archive = Path(temporary) / 'update.tar.gz'
                archive.write_bytes(data)
                installed = self.install(archive, tag)
            self.status('updated', 'Update geinstalleerd: ' + installed, version=installed, previous=current)
            return True
        except (OSError, ValueError, KeyError, StopIteration, tarfile.TarError) as error:
            self.status('offline-or-error', 'Update overgeslagen; bestaande versie blijft beschikbaar.', version=current, reason=type(error).__name__)
            return False

    def boot_system(self):
        if self.current_version() == '0.0.0':
            self.install(self.boot / 'seed.tar.gz', '0.1.0')
        self.configure_first_boot()
        self.update()

    def rollback(self):
        previous = self.state / 'previous'
        if not previous.is_symlink():
            raise ValueError('Er is nog geen vorige versie.')
        target = previous.resolve()
        rejected = self.current_version()
        self.activate(target)
        (self.state / 'rejected-version').write_text(rejected + '\n')
        self.status('rolled-back', 'Vorige versie teruggezet.', version=self.current_version())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('boot', 'update', 'rollback'))
    args = parser.parse_args()
    console = Console()
    # De bootstrap op FAT blijft klein; voer na installatie de actieve runtime uit.
    active = console.state / 'current/runtime.py'
    if active.exists() and Path(__file__).resolve() != active.resolve():
        os.execv(sys.executable, [sys.executable, str(active), args.action])
    if args.action == 'boot':
        console.boot_system()
    elif args.action == 'update':
        console.update()
    else:
        console.rollback()


if __name__ == '__main__':
    main()
