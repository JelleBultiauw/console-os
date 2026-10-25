import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flash_usb', ROOT / 'tools/flash-usb-macos.py')
flash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flash)


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.disk = dict(Internal=False, BusProtocol='USB', VirtualOrPhysical='Physical', TotalSize=32000, Writable=True)
        self.partition = dict(VolumeUUID='EXPECTED')

    def validate(self, disk=None, partition=None):
        with patch.object(flash, 'disk_info', side_effect=[disk or self.disk, partition or self.partition]):
            flash.validate_target('/dev/disk9', 32000, 'EXPECTED')

    def test_accepts_only_matching_usb(self):
        self.validate()

    def test_rejects_internal_disk(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.disk, Internal=True))

    def test_rejects_other_capacity(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.disk, TotalSize=64000))

    def test_rejects_other_physical_stick(self):
        with self.assertRaises(ValueError):
            self.validate(partition=dict(VolumeUUID='OTHER'))

    def test_rejects_virtual_device(self):
        with self.assertRaises(ValueError):
            self.validate(dict(self.disk, VirtualOrPhysical='Virtual'))

    def test_rejects_partition_target_before_query(self):
        with patch.object(flash, 'disk_info') as query, self.assertRaises(ValueError):
            flash.validate_target('/dev/disk9s1', 32000, 'EXPECTED')
        query.assert_not_called()
