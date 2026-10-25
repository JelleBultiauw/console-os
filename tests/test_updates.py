import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('console_runtime', ROOT / 'payload/runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def package(version='0.1.0', extra=None, architecture='x86_64'):
    files = {p.relative_to(ROOT / 'payload').as_posix(): p.read_bytes() for p in (ROOT / 'payload').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    manifest = json.loads(files['manifest.json'])
    manifest.update(version=version, architecture=architecture)
    files['manifest.json'] = json.dumps(manifest).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if extra:
            archive.addfile(extra, io.BytesIO(b'x' * extra.size) if extra.isfile() else None)
    return buffer.getvalue()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.console = runtime.Console(self.root / 'state', self.root / 'boot', self.root / 'userdata')
        self.console.boot.mkdir()
        (self.console.boot / 'seed.tar.gz').write_bytes(package())
        (self.console.boot / 'config.json').write_text((ROOT / 'boot/config.json').read_text())
        self.console.install(self.console.boot / 'seed.tar.gz')

    def tearDown(self):
        self.temp.cleanup()

    def server(self, version='0.2.0', data=None, digest=None):
        data = data if data is not None else package(version)
        digest = digest or hashlib.sha256(data).hexdigest()
        prefix = 'https://github.com/JelleBultiauw/console-os/releases/download/v' + version + '/'
        release = {'tag_name': 'v' + version, 'draft': False, 'prerelease': False, 'assets': [
            {'name': 'console-os-update.tar.gz', 'size': len(data), 'browser_download_url': prefix + 'console-os-update.tar.gz'},
            {'name': 'console-os-update.tar.gz.sha256', 'size': 92, 'browser_download_url': prefix + 'console-os-update.tar.gz.sha256'}]}
        def request(url, limit):
            if url.endswith('/releases/latest'):
                return json.dumps(release).encode()
            if url.endswith('.sha256'):
                return (digest + '  console-os-update.tar.gz\n').encode()
            return data
        self.console.request = Mock(side_effect=request)
        return release

    def test_seed_and_settings_are_idempotent(self):
        self.console.configure_first_boot()
        path = self.console.userdata / 'system/batocera.conf'
        path.write_text(path.read_text() + 'my.preference=yes\n')
        before = path.read_text()
        self.console.configure_first_boot()
        self.assertEqual(before, path.read_text())
        self.assertTrue((self.console.userdata / 'themes/console-os/theme.xml').is_file())

    def test_same_version_does_not_download_or_install(self):
        self.server('0.1.0')
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.request.call_count, 1)

    def test_older_version_does_not_downgrade(self):
        self.server('0.0.9')
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.current_version(), '0.1.0')

    def test_update_keeps_previous_and_never_touches_games(self):
        save = self.console.userdata / 'saves/keep-me.sav'
        save.parent.mkdir(parents=True)
        save.write_bytes(b'GAME SAVE')
        self.server()
        self.assertTrue(self.console.update())
        self.assertEqual(self.console.current_version(), '0.2.0')
        self.assertEqual(runtime.read_json(self.console.state / 'previous/manifest.json')['version'], '0.1.0')
        self.assertEqual(save.read_bytes(), b'GAME SAVE')

    def test_checksum_failure_keeps_current(self):
        self.server(digest='0' * 64)
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.current_version(), '0.1.0')

    def test_network_failure_still_completes_boot(self):
        self.console.request = Mock(side_effect=OSError('offline'))
        self.console.boot_system()
        self.assertEqual(self.console.current_version(), '0.1.0')
        self.assertEqual(runtime.read_json(self.console.state / 'status.json')['state'], 'offline-or-error')

    def test_archive_path_escape_is_rejected(self):
        bad = tarfile.TarInfo('../escape')
        bad.size = 1
        self.server(data=package('0.2.0', bad))
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.current_version(), '0.1.0')
        self.assertFalse((self.console.state / 'releases/escape').exists())

    def test_symlink_is_rejected(self):
        bad = tarfile.TarInfo('theme/escape')
        bad.type = tarfile.SYMTYPE
        bad.linkname = '/etc/passwd'
        self.server(data=package('0.2.0', bad))
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.current_version(), '0.1.0')

    def test_wrong_cpu_target_is_rejected(self):
        self.server(data=package('0.2.0', architecture='x86-64-v3'))
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.current_version(), '0.1.0')

    def test_release_cannot_redirect_to_another_repository(self):
        release = self.server()
        release['assets'][0]['browser_download_url'] = 'https://github.com/other/other/releases/download/v0.2.0/update'
        self.assertFalse(self.console.update())
        self.assertEqual(self.console.request.call_count, 1)

    def test_rollback_is_not_immediately_undone(self):
        self.server()
        self.console.update()
        self.console.rollback()
        self.assertEqual(self.console.current_version(), '0.1.0')
        self.assertFalse(self.console.update())
        self.assertEqual(runtime.read_json(self.console.state / 'status.json')['state'], 'held-back')

    def test_incomplete_or_prerelease_tags_are_rejected(self):
        for value in ('v1.0', '1.0.0-rc1', '../1.0.0', '01.0.0'):
            with self.assertRaises(ValueError):
                runtime.version_tuple(value)

    def test_ram_fallback_does_not_download_updates(self):
        self.console.temporary_storage = Mock(return_value=True)
        self.console.request = Mock()
        self.console.boot_system()
        self.console.request.assert_not_called()
        self.assertEqual(runtime.read_json(self.console.state / 'status.json')['state'], 'temporary-storage')

    def test_error_report_retains_network_cause(self):
        self.console.request = Mock(side_effect=urllib.error.URLError('Network unreachable'))
        self.assertFalse(self.console.update())
        self.assertEqual(runtime.read_json(self.console.state / 'status.json')['detail'], 'Network unreachable')

    def test_fresh_boot_accepts_newer_seed(self):
        fresh = runtime.Console(self.root / 'fresh-state', self.root / 'fresh-boot', self.root / 'fresh-userdata')
        fresh.boot.mkdir()
        (fresh.boot / 'seed.tar.gz').write_bytes(package('0.1.1'))
        (fresh.boot / 'config.json').write_text((ROOT / 'boot/config.json').read_text())
        fresh.request = Mock(side_effect=OSError('offline'))
        fresh.boot_system()
        self.assertEqual(fresh.current_version(), '0.1.1')


if __name__ == '__main__':
    unittest.main()
