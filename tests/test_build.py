import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build


class BuildTests(unittest.TestCase):
    def check_variant(self, variant, app_id):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'openviking', root / 'openviking', ignore=shutil.ignore_patterns('__pycache__'))
            tool = root / 'fake-fnpack'
            tool.touch()
            model = root / 'test.gguf'
            model.write_bytes(b'test-only-model')
            args = argparse.Namespace(fnpack=str(tool), variant=variant, app_id=app_id,
                image='sha256:' + '0' * 64, preloaded_image=True, image_archive=None,
                model=str(model), model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                arch='arm64', version='0.4.16-9', container_build=False)

            def fake_pack(command, cwd, check):
                stage = Path(cwd)
                manifest = (stage / 'manifest').read_text(encoding='utf-8')
                fields = {k.strip(): v.strip() for k, v in (line.split('=', 1) for line in manifest.splitlines() if '=' in line)}
                self.assertEqual(fields['appname'], app_id)
                self.assertEqual(fields['display_name'], 'OpenViking')
                entry = json.loads((stage / 'app/ui/config').read_text())['.url'][app_id + '.main']
                self.assertEqual(entry['title'], 'OpenViking')
                self.assertEqual(entry['url'], '/studio/fnos.html')
                resources = json.loads((stage / 'config/resource').read_text())
                self.assertEqual(len(resources['data-share']['shares']), 2)
                self.assertNotIn('docker-project', resources)
                compose = (stage / 'app/docker/docker-compose.yaml').read_text()
                self.assertNotIn('/models:/models', compose)
                expected = 'openviking-fnos-local' if app_id == 'openviking-local' else 'openviking-fnos'
                self.assertIn('container_name: ' + expected + '\n', compose)
                with tarfile.open(stage / 'test.fpk', 'w') as archive:
                    archive.add(stage / 'manifest', arcname='manifest')

            with patch.object(build, 'ROOT', root), patch.object(build.subprocess, 'run', side_effect=fake_pack):
                build.build(args)

    def test_new_local_package(self):
        self.check_variant('local', 'openviking')

    def test_legacy_upgrade_keeps_id_not_display_suffix(self):
        self.check_variant('local', 'openviking-local')

    def test_standard_preserves_data_shares(self):
        self.check_variant('standard', 'openviking')


if __name__ == '__main__':
    unittest.main()
