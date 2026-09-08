"""Run in the image with host network and read-only installed config at /config/ov.conf."""
import json
import os
from pathlib import Path
import time
import requests

base = 'http://127.0.0.1:1933'
with open('/config/ov.conf') as stream:
    config = json.load(stream)
assert 'vlm' not in config
session = requests.Session()
session.headers['X-API-Key'] = config['server']['root_api_key']
for attempt in range(60):
    try:
        response = session.get(base + '/ready', timeout=3)
        if response.status_code == 200:
            break
    except requests.RequestException:
        pass
    time.sleep(1)
else:
    raise RuntimeError('Server not ready')
for path in ['/health', '/ready', '/studio/']:
    response = session.get(base + path, timeout=10)
    print(path, response.status_code, flush=True)
    response.raise_for_status()
schema = session.get(base + '/openapi.json', timeout=10).json()
paths = schema['paths']
upload = next(p for p in paths if p.endswith('/resources/temp_upload'))
add = next(p for p in paths if p.endswith('/resources'))
find = next(p for p in paths if p.endswith('/find'))
unauthorized = requests.post(base + find, json={'query': 'NAS'}, timeout=10)
assert unauthorized.status_code in (401, 403), unauthorized.status_code
print('unauthenticated_rejected', unauthorized.status_code, flush=True)
stamp = str(int(time.time()))
credentials = Path('/tests/smoke-user.json')
if credentials.exists():
    user_key = json.loads(credentials.read_text())['user_key']
else:
    response = session.post(base + '/api/v1/admin/accounts',
        json={'account_id': 'fpk-smoke-' + stamp, 'admin_user_id': 'tester'}, timeout=30)
    response.raise_for_status()
    account = response.json()['result']
    with os.fdopen(os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(account, stream)
    user_key = account['user_key']
session.headers['X-API-Key'] = user_key
documents = [('nas', '飞牛 NAS 可以通过 Docker 容器部署应用并保存文件。'),
             ('fruit', '香蕉和苹果是常见水果，可以制作果汁。')]
verify_uri = os.environ.get('SMOKE_VERIFY_URI')
for name, content in ([] if verify_uri else documents):
    response = session.post(base + upload, files={'file': (name + '.txt', content.encode(), 'text/plain')}, timeout=30)
    response.raise_for_status()
    data = response.json()
    print('upload', json.dumps(data, ensure_ascii=False), flush=True)
    temp_id = data.get('result', data)['temp_file_id']
    response = session.post(base + add, json={'temp_file_id': temp_id,
        'to': 'viking://resources/fpk-smoke-' + stamp + '/' + name,
        'create_parent': True, 'wait': True, 'timeout': 90}, timeout=120)
    print('ingest', response.status_code, response.text[:2500], flush=True)
    response.raise_for_status()
response = session.post(base + find, json={'query': '如何在 NAS 上部署 Docker 应用？',
    'target_uri': verify_uri or 'viking://resources/fpk-smoke-' + stamp, 'limit': 5}, timeout=60)
print('find', response.status_code, response.text[:5000], flush=True)
response.raise_for_status()
result = response.json()['result']
resources = result['resources']
assert resources and '/nas' in resources[0]['uri'], resources
print('HTTP_SMOKE_PASSED', flush=True)
