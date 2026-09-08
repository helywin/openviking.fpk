import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('configure', Path(__file__).resolve().parents[1] / 'openviking/app/tools/configure.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ConfigurationTests(unittest.TestCase):
    def values(self):
        return dict(zip(config.FIELDS, ['r' * 32, 'http://embedding:8080/v1', 'embed-model', '', '512']))

    def test_round_trip_and_secret_escaping(self):
        values = self.values()
        values['embed_key'] = 'a"\\\n$()中文'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config.apply_config(root, values, 'standard')
            path = root / 'openviking/ov.conf'
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['embedding']['dense']['api_key'], values['embed_key'])
            config.apply_config(root, dict.fromkeys(config.FIELDS, ''), 'standard')
            self.assertTrue(path.with_suffix('.conf.previous').exists())
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['embedding']['dense']['api_key'], values['embed_key'])

    def test_invalid_update_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = self.values()
            config.apply_config(root, values, 'standard')
            path = root / 'openviking/ov.conf'
            before = path.read_bytes()
            values['embed_model'] = 'different-model'
            with self.assertRaises(ValueError):
                config.apply_config(root, values, 'standard')
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_endpoint_and_dimension(self):
        for key, value in [('embed_base', 'file:///etc/passwd'), ('embed_base', 'https://user:pass@host/v1'),
                           ('embed_dimension', 'no'), ('root_key', 'short')]:
            values = self.values()
            values[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                config.make_config(values, 'standard')

    def test_local_mode_needs_no_remote_embedding(self):
        values = self.values()
        for key in values:
            if key.startswith('embed_'):
                values[key] = ''
        result = config.make_config(values, 'local')
        self.assertNotIn('vlm', result)
        self.assertEqual(result['embedding']['dense']['dimension'], 512)
        self.assertEqual(result['embedding']['dense']['model_path'], '/models/bge-small-zh-v1.5-f16.gguf')


if __name__ == '__main__':
    unittest.main()
