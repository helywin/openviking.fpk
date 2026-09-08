import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'openviking/app/tools'))
import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bundle = self.root / 'bundle'
        self.shared = self.root / 'shared'
        self.bundle.mkdir()
        self.shared.mkdir()
        (self.bundle / storage.MODEL).write_bytes(b'test-model')
        self.digest = hashlib.sha256(b'test-model').hexdigest()

    def test_seed_validates_and_keeps_existing_model(self):
        storage.seed_model(self.bundle, self.shared, self.digest)
        self.assertEqual((self.shared / storage.MODEL).read_bytes(), b'test-model')
        storage.seed_model(self.bundle, self.shared, self.digest)
        self.assertEqual(list(self.shared.iterdir()), [self.shared / storage.MODEL])

    def test_never_overwrite_changed_shared_model(self):
        (self.shared / storage.MODEL).write_bytes(b'changed-model')
        with self.assertRaises(ValueError):
            storage.seed_model(self.bundle, self.shared, self.digest)
        self.assertEqual((self.shared / storage.MODEL).read_bytes(), b'changed-model')

    def test_reject_corrupt_bundle(self):
        with self.assertRaises(ValueError):
            storage.seed_model(self.bundle, self.shared, '0' * 64)
        self.assertEqual(list(self.shared.iterdir()), [])

    def test_only_dedicated_shares_are_mounted_readonly(self):
        plan = storage.mount_plan('/vol2/@appshare/openviking/documents',
                                  '/vol2/@appshare/openviking/models', 'local')
        mounts = plan['services']['openviking']['volumes']
        self.assertEqual([m['target'] for m in mounts], ['/nas/documents', '/models'])
        self.assertTrue(all(m['read_only'] and not m['bind']['create_host_path'] for m in mounts))
        for bad in ('/', '/etc', '/vol1/../openviking/documents'):
            with self.assertRaises(ValueError):
                storage.mount_plan(bad, '/vol1/openviking/models', 'local')

    def test_source_declares_both_shares_and_no_auto_docker_project(self):
        resource = json.loads((ROOT / 'openviking/config/resource').read_text())
        self.assertEqual([v['name'] for v in resource['data-share']['shares']],
                         ['openviking/models', 'openviking/documents'])
        self.assertNotIn('docker-project', resource)


if __name__ == '__main__':
    unittest.main()
