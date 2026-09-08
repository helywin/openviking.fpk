"""Protect the port-service route verified through the native FN Connect link."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EntryTests(unittest.TestCase):
    def test_port_entry_has_no_system_gateway_prefix(self):
        config = json.loads((ROOT / 'openviking/app/ui/config').read_text())
        entry = config['.url']['openviking.main']
        self.assertEqual(entry['type'], 'url')
        self.assertEqual(entry['port'], '1933')
        self.assertEqual(entry['url'], '/studio/fnos.html')
        self.assertNotIn('gatewayPrefix', entry)
        self.assertNotIn('gatewaySocket', entry)

    def test_manifest_and_entry_identity_match(self):
        fields = dict(line.split('=', 1) for line in (ROOT / 'openviking/manifest').read_text(encoding='utf-8').splitlines() if '=' in line)
        fields = {k.strip(): v.strip() for k, v in fields.items()}
        self.assertEqual(fields['appname'], 'openviking')
        self.assertEqual(fields['desktop_applaunchname'], 'openviking.main')
        entry = json.loads((ROOT / 'openviking/app/ui/config').read_text())['.url']['openviking.main']
        self.assertEqual(entry['url'], '/studio/fnos.html')
        self.assertNotIn('/app/', entry['url'])


if __name__ == '__main__':
    unittest.main()
