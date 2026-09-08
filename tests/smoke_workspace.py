"""Validate auto-provisioned workspace, session CRUD and tenant isolation."""
import json
from pathlib import Path
import uuid
import requests

base = 'http://127.0.0.1:1933'
workspace = json.loads(Path('/config/fnos-workspace.json').read_text())
session = requests.Session()
session.headers['X-API-Key'] = workspace['user_key']
sid = 'fpk-session-' + uuid.uuid4().hex
path = '/api/v1/sessions/' + sid


def call(method, url, **kwargs):
    response = session.request(method, base + url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


call('POST', '/api/v1/sessions', json={'session_id': sid})
try:
    call('POST', path + '/messages', json={'role': 'user', 'content': '飞牛本地纯文本会话验收'})
    result = call('GET', path + '/context')
    assert '飞牛本地纯文本会话验收' in json.dumps(result, ensure_ascii=False)
    assert sid in json.dumps(call('GET', '/api/v1/sessions'))
    other_key = json.loads(Path('/tests/smoke-user.json').read_text())['user_key']
    other = requests.get(base + path, headers={'X-API-Key': other_key}, timeout=10)
    assert other.status_code in (403, 404), other.status_code
    unauthenticated = requests.get(base + path, timeout=10)
    assert unauthenticated.status_code == 401
    print('AUTO_WORKSPACE_SESSION_AND_TENANT_ISOLATION_PASSED')
finally:
    call('DELETE', path)
assert session.get(base + path, timeout=10).status_code == 404
print('TEST_SESSION_DELETE_PASSED')
