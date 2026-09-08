"""Run via docker exec inside the installed container. Uses only a test document."""
import errno
import hashlib
import json
from pathlib import Path
import uuid

import requests

documents = Path('/nas/documents')
sample = documents / 'nas-storage-check.txt'
assert 'OpenViking NAS' in sample.read_text(encoding='utf-8')
model = Path('/models/bge-small-zh-v1.5-f16.gguf')
digest = hashlib.sha256()
with model.open('rb') as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
assert digest.hexdigest() == 'ab9b81d9cd329c712eee379cf0068eabe6a5e2a01d0def61535eba9384085e2c'
for folder in (documents, model.parent):
    probe = folder / ('.fpk-readonly-check-' + uuid.uuid4().hex)
    try:
        with probe.open('xb') as stream:
            stream.write(b'test')
    except OSError as error:
        assert error.errno in (errno.EROFS, errno.EACCES), error.errno
    else:
        probe.unlink()
        raise AssertionError('Dedicated share must be read-only inside the container')

record = json.loads(Path('/app/.openviking/fnos-workspace.json').read_text())
session = requests.Session()
session.trust_env = False
session.headers['X-API-Key'] = record['user_key']
base = 'http://127.0.0.1:1933'
with sample.open('rb') as source:
    response = session.post(base + '/api/v1/resources/temp_upload',
                            files={'file': (sample.name, source, 'text/plain')}, timeout=30)
response.raise_for_status()
temporary = response.json()['result']['temp_file_id']
target = 'viking://resources/fpk-nas-storage-' + uuid.uuid4().hex[:12]
response = session.post(base + '/api/v1/resources', json={'temp_file_id': temporary,
                        'to': target, 'create_parent': True, 'wait': True, 'timeout': 90}, timeout=120)
response.raise_for_status()
response = session.post(base + '/api/v1/search/find', json={'query': 'NAS 的模型和文档保存在什么目录？',
                        'target_uri': target, 'limit': 5}, timeout=60)
response.raise_for_status()
resources = response.json()['result']['resources']
assert resources and 'nas-storage-check' in resources[0]['uri'], 'Test document was not retrieved'
print('NAS_SHARED_MODEL_AND_DOCUMENT_READONLY_AND_INGEST_PASSED')
print('Test resource:', target)
