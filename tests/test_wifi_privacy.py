import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wifi = load('import_wifi', 'boot/import-wifi.py')
release = load('build_release', 'build-release.py')


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile = self.root / 'system/console-os/wifi.local.json'
        self.profile.parent.mkdir(parents=True)
        # Uitsluitend fictieve testgegevens, geen gegevens van de gebruiker.
        self.value = dict(ssid='Example network', password='fake$;# passphrase', country='BE')
        self.profile.write_text(json.dumps(self.value))

    def tearDown(self):
        self.temp.cleanup()

    def test_configures_without_shell_and_removes_import_file(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0))
        self.assertTrue(wifi.import_profile(self.profile, runner, '/dev/sdb2 /userdata ext4 rw 0 0'))
        args = runner.call_args.args[0]
        self.assertEqual(args, ['/usr/bin/batocera-wifi', 'enable', self.value['ssid'], self.value['password'], 'BE'])
        self.assertNotIn('shell', runner.call_args.kwargs)
        self.assertEqual(runner.call_args.kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(runner.call_args.kwargs['stderr'], subprocess.DEVNULL)
        self.assertFalse(self.profile.exists())
        self.assertNotIn(self.value['password'], self.profile.with_name('wifi-import-status.json').read_text())

    def test_ram_fallback_keeps_profile_and_never_calls_helper(self):
        runner = Mock()
        with self.assertRaises(RuntimeError):
            wifi.import_profile(self.profile, runner, 'tmpfs /userdata tmpfs rw 0 0')
        runner.assert_not_called()
        self.assertTrue(self.profile.exists())

    def test_failed_configuration_keeps_profile(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1))
        with self.assertRaises(RuntimeError):
            wifi.import_profile(self.profile, runner, '/dev/sdb2 /userdata ext4 rw 0 0')
        self.assertTrue(self.profile.exists())

    def test_line_injection_is_rejected(self):
        for key in ('ssid', 'password'):
            with self.assertRaises(ValueError):
                wifi.validate_profile(dict(self.value, **{key: 'bad\nsetting=value'}))

    def test_missing_profile_does_nothing(self):
        self.profile.unlink()
        runner = Mock()
        self.assertFalse(wifi.import_profile(self.profile, runner, ''))
        runner.assert_not_called()


class ReleasePrivacyTests(unittest.TestCase):
    def test_secret_and_local_payload_files_are_rejected(self):
        for relative in ('private/wifi.local.json', 'wifi.local.json', 'theme/wifi.local.json', '.env', 'unknown.json'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                payload = Path(tmp)
                p = payload / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fictitious private data')
                with self.assertRaises(ValueError):
                    list(release.payload_files(payload))

    def test_symlink_cannot_include_an_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);payload = root / 'payload';(payload/'theme').mkdir(parents=True)
            outside = root / 'outside';outside.write_text('fictitious secret')
            (payload/'theme/image.svg').symlink_to(outside)
            with self.assertRaises(ValueError):
                list(release.payload_files(payload))

    def test_existing_payload_is_allowed(self):
        files = list(release.payload_files(ROOT/'payload'))
        self.assertTrue(files)
        self.assertTrue(any(p.name == 'manifest.json' for p in files))
