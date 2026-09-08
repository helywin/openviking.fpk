import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('configure', Path(__file__).resolve().parents[1] / 'openviking/app/tools/configure.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class SnapshotTests(unittest.TestCase):
    def test_backup_restore_and_preserve_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'openviking/data').mkdir(parents=True)
            (root / 'openviking/data/text').write_text('original')
            config.backup_state(root)
            snapshot = next((root / 'backups').iterdir()).name
            (root / 'openviking/data/text').write_text('new')
            config.restore_state(root, snapshot)
            self.assertEqual((root / 'openviking/data/text').read_text(), 'original')
            previous = next(root.glob('pre-restore-*'))
            self.assertEqual((previous / 'data/text').read_text(), 'new')

    def test_tampered_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'openviking').mkdir()
            (root / 'openviking/data').write_text('original')
            config.backup_state(root)
            snapshot = next((root / 'backups').iterdir())
            (snapshot / 'openviking/data').write_text('bad')
            with self.assertRaises(ValueError):
                config.restore_state(root, snapshot.name)
            self.assertEqual((root / 'openviking/data').read_text(), 'original')

    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ['../outside', '/etc', '..', 'a\\b']:
                with self.assertRaises(ValueError):
                    config.restore_state(Path(directory), name)
