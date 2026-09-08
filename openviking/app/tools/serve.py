"""Supervise upstream server and provision one usable workspace on first start."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.error
import urllib.request

from configure import atomic_json

STATE = Path('/app/.openviking')


def api(path, root_key, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request('http://127.0.0.1:1933' + path, data=data,
        headers={'X-API-Key': root_key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def provision():
    config = json.loads((STATE / 'ov.conf').read_text())
    root_key = config['server']['root_api_key']
    record_path = STATE / 'fnos-workspace.json'
    if record_path.is_symlink():
        raise ValueError('Invalid workspace record')
    accounts = api('/api/v1/admin/accounts', root_key)['result']
    if record_path.exists():
        os.chmod(record_path, 0o600)
        record = json.loads(record_path.read_text())
        if not any(a['account_id'] == record['account_id'] for a in accounts):
            raise ValueError('Workspace metadata and database disagree; restore matching backup')
        return
    account_id = 'fnos'
    # An existing user-created workspace is never overwritten or assigned a new key.
    if any(a['account_id'] == account_id for a in accounts):
        atomic_json(record_path, {'account_id': account_id, 'existing': True})
        return
    # Deterministic seed permits retry after an interrupted first-start request.
    seed = hashlib.sha256(('fnos-initial-workspace\0' + root_key).encode()).hexdigest()
    result = api('/api/v1/admin/accounts', root_key,
                 {'account_id': account_id, 'admin_user_id': 'owner', 'seed': seed})['result']
    atomic_json(record_path, result)


def main():
    ready = STATE / '.fnos-ready'
    ready.unlink(missing_ok=True)
    child = subprocess.Popen(['openviking-entrypoint'], start_new_session=True)

    def stop(signum, frame):
        if child.poll() is None:
            os.killpg(child.pid, signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for attempt in range(120):
            if child.poll() is not None:
                raise RuntimeError('Upstream exited before ready')
            try:
                with urllib.request.urlopen('http://127.0.0.1:1933/ready', timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Upstream readiness timeout')
        provision()
        ready.touch(mode=0o600)
        print('fnOS workspace initialized; no credentials are written to logs.', flush=True)
        return child.wait()
    except Exception:
        print('fnOS initialization failed; inspect readiness and restore a matching backup if needed.', flush=True)
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        return 1
    finally:
        ready.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
