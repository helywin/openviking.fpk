import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'openviking/app/tools'
sys.path.insert(0, str(TOOLS))
import serve
sys.path.pop(0)


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name)
        (self.state / 'ov.conf').write_text(json.dumps({'server': {'root_api_key': 'test-only-key'}}))
        self.state_patch = patch.object(serve, 'STATE', self.state)
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)

    def test_new_workspace_records_credentials_once(self):
        created = {'account_id': 'fnos', 'user_key': 'test-user-key'}
        with patch.object(serve, 'api', side_effect=[{'result': []}, {'result': created}]) as api:
            serve.provision()
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args.args[2]['admin_user_id'], 'owner')
        self.assertEqual(json.loads((self.state / 'fnos-workspace.json').read_text()), created)
        with patch.object(serve, 'api', return_value={'result': [{'account_id': 'fnos'}]}) as api:
            serve.provision()
            self.assertEqual(api.call_count, 1)

    def test_existing_workspace_is_not_overwritten(self):
        with patch.object(serve, 'api', return_value={'result': [{'account_id': 'fnos'}]}) as api:
            serve.provision()
            self.assertEqual(api.call_count, 1)
        self.assertEqual(json.loads((self.state / 'fnos-workspace.json').read_text()),
                         {'account_id': 'fnos', 'existing': True})

    def test_missing_recorded_workspace_fails_closed(self):
        (self.state / 'fnos-workspace.json').write_text('{"account_id":"fnos"}')
        with patch.object(serve, 'api', return_value={'result': []}):
            with self.assertRaisesRegex(ValueError, 'disagree'):
                serve.provision()


if __name__ == '__main__':
    unittest.main()
