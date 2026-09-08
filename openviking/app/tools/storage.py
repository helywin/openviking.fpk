"""Prepare dedicated NAS shares without sharing private config or workspace keys."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

from configure import atomic_json

MODEL = 'bge-small-zh-v1.5-f16.gguf'
MODEL_SHA256 = 'ab9b81d9cd329c712eee379cf0068eabe6a5e2a01d0def61535eba9384085e2c'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def seed_model(bundled, shared, expected=MODEL_SHA256):
    source, target = bundled / MODEL, shared / MODEL
    if source.is_symlink() or target.is_symlink():
        raise ValueError('Model must not be a symbolic link')
    if target.exists():
        if digest(target) != expected:
            raise ValueError('Existing shared model does not match the fixed embedding model')
        return
    if digest(source) != expected:
        raise ValueError('Bundled model checksum mismatch')
    fd, name = tempfile.mkstemp(prefix='.model-', dir=shared)
    staging = Path(name)
    try:
        with os.fdopen(fd, 'wb') as out, source.open('rb') as src:
            shutil.copyfileobj(src, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        if digest(staging) != expected:
            raise ValueError('Model copy checksum mismatch')
        os.chmod(staging, 0o644)
        # Atomic no-clobber publication, even if another process created target.
        os.link(staging, target)
    finally:
        staging.unlink(missing_ok=True)


def mount_plan(documents, models, variant):
    if variant not in ('local', 'standard'):
        raise ValueError('Invalid variant')
    for path, suffix in ((documents, '/openviking/documents'), (models, '/openviking/models')):
        if not path.startswith('/') or not path.endswith(suffix) or '..' in PurePosixPath(path).parts:
            raise ValueError('Invalid dedicated share')
    mounts = [{'type': 'bind', 'source': documents, 'target': '/nas/documents',
               'read_only': True, 'bind': {'create_host_path': False}}]
    if variant == 'local':
        mounts.append({'type': 'bind', 'source': models, 'target': '/models',
                       'read_only': True, 'bind': {'create_host_path': False}})
    return {'services': {'openviking': {'volumes': mounts}}}


def main():
    fields = sys.stdin.buffer.read(32769).decode('utf-8').split('\0')
    if len(fields) != 4 or fields[-1] or sum(map(len, fields)) > 32768:
        raise ValueError('Invalid storage inputs')
    documents, models, variant, _ = fields
    plan = mount_plan(documents, models, variant)
    if variant == 'local':
        seed_model(Path('/bundled-models'), Path('/shared-models'))
    atomic_json(Path('/state/nas-volumes.json'), plan)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('NAS 专用目录或固定模型校验失败，未覆盖已有模型。', file=sys.stderr)
        raise SystemExit(1)
