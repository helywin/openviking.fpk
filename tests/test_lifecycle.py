"""Exercise the renamed local package without touching a real Docker daemon."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CMD = Path(__file__).resolve().parents[1] / 'openviking/cmd'


@unittest.skipIf(os.name == 'nt', 'Linux lifecycle scripts')
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'settings.json').write_text(json.dumps({'image': 'test-image', 'variant': 'local'}))
        docker = self.root / 'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
                          'if [ "$1" = inspect ]; then printf "healthy\\n"; fi\n')
        docker.chmod(0o755)
        self.documents = self.root / 'shares/openviking/documents'
        self.models = self.root / 'shares/openviking/models'
        self.documents.mkdir(parents=True)
        self.models.mkdir()
        (self.root / 'nas-volumes.json').write_text('{}')
        self.env = dict(os.environ, PATH=str(self.root) + ':' + os.environ['PATH'],
                        TRIM_APPNAME='openviking', TRIM_APPDEST=str(self.root),
                        TRIM_PKGVAR=str(self.root), CALL_LOG=str(self.root / 'calls'),
                        TRIM_DATA_SHARE_PATHS=str(self.documents) + ':' + str(self.models))

    def run_script(self, script, *args):
        subprocess.run(['bash', str(CMD / script), *args], env=self.env, check=True, capture_output=True)
        return (self.root / 'calls').read_text()

    def test_local_start_uses_variant_and_new_container(self):
        calls = self.run_script('main', 'start')
        self.assertIn('compose -p openviking ', calls)
        self.assertIn('up -d --pull never', calls)
        self.assertIn('openviking-fnos', calls)
        self.assertNotIn('openviking-local', calls)

    def test_legacy_install_keeps_its_container_and_project(self):
        self.env['TRIM_APPNAME'] = 'openviking-local'
        calls = self.run_script('main', 'start')
        self.assertIn('compose -p openviking-local ', calls)
        self.assertIn('openviking-fnos-local', calls)

    def test_missing_share_fails_before_compose(self):
        self.env['TRIM_DATA_SHARE_PATHS'] = ''
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_script('main', 'start')
        self.assertNotIn('compose ', (self.root / 'calls').read_text())

    def test_local_stop(self):
        calls = self.run_script('main', 'stop')
        self.assertIn('stop --timeout 30', calls)

    def test_keep_data_uninstall_only_removes_own_project(self):
        calls = self.run_script('uninstall_init')
        self.assertIn('compose -p openviking ', calls)
        self.assertIn('down --timeout 30', calls)
        self.assertNotIn('--volumes', calls)
        self.assertNotIn(' delete', calls)


if __name__ == '__main__':
    unittest.main()
