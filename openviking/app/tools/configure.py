"""FPK configuration helper. Invoked in an isolated container; secrets arrive on stdin."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit

FIELDS = ('root_key', 'embed_base', 'embed_model', 'embed_key', 'embed_dimension')


def tree_hashes(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Backup cannot contain symbolic links')
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def backup_state(state):
    source = state / 'openviking'
    backups = state / 'backups'
    if source.is_symlink() or backups.is_symlink():
        raise ValueError('Invalid backup directory')
    if not source.exists():
        return
    before = tree_hashes(source)
    size = sum(p.stat().st_size for p in source.rglob('*') if p.is_file())
    if shutil.disk_usage(state).free < size + 64 * 1024 * 1024:
        raise ValueError('Insufficient space for snapshot')
    backups.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    temporary = backups / ('.pending-' + stamp)
    temporary.mkdir(mode=0o700)
    shutil.copytree(source, temporary / 'openviking')
    if tree_hashes(temporary / 'openviking') != before or tree_hashes(source) != before:
        raise ValueError('Snapshot changed during backup')
    atomic_json(temporary / 'snapshot.json', {'format': 1, 'files': before})
    temporary.rename(backups / stamp)


def restore_state(state, snapshot):
    if not snapshot or '/' in snapshot or '\\' in snapshot or snapshot.startswith('.'):
        raise ValueError('Invalid snapshot name')
    parent = state / 'backups'
    source = parent / snapshot
    if parent.is_symlink() or source.is_symlink() or (source / 'openviking').is_symlink():
        raise ValueError('Invalid snapshot location')
    manifest = json.loads((source / 'snapshot.json').read_text())
    if manifest.get('format') != 1 or tree_hashes(source / 'openviking') != manifest['files']:
        raise ValueError('Snapshot checksum mismatch')
    target = state / 'openviking'
    if target.is_symlink():
        raise ValueError('Invalid restore target')
    replacement = state / ('.restore-' + snapshot)
    if replacement.exists():
        raise ValueError('Previous restore staging exists')
    shutil.copytree(source / 'openviking', replacement)
    if tree_hashes(replacement) != manifest['files']:
        raise ValueError('Restore checksum mismatch')
    preserved = state / ('pre-restore-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    if target.exists():
        target.rename(preserved)
    replacement.rename(target)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.config-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), 0o600)
            else:
                os.chmod(name, 0o600)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def endpoint(value, label):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError(label + ': 需要完整的 HTTP(S) API 地址')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(label + ': 地址不得包含凭据、查询参数或 fragment')
    return value.rstrip('/')


def make_config(values, variant, old=None):
    if variant not in ('standard', 'local'):
        raise ValueError('未知的安装模式')
    config = copy.deepcopy(old) if old else {}
    server = config.setdefault('server', {})
    root_key = values['root_key'] or server.get('root_api_key', '')
    if len(root_key) < 24:
        raise ValueError('Root API Key 至少需要 24 个字符')
    server.update(port=1933, root_api_key=root_key)
    config.setdefault('storage', {}).update(
        workspace='/app/.openviking/data',
        agfs={'backend': 'local'}, vectordb={'backend': 'local', 'name': 'context'})
    # Pure text mode: no external generative model and no placeholder credentials.
    config.pop('vlm', None)
    previous = config.get('embedding', {}).get('dense')
    if variant == 'local':
        dense = dict(provider='local', model='bge-small-zh-v1.5-f16',
                     model_path='/models/bge-small-zh-v1.5-f16.gguf', dimension=512, input='text')
    else:
        dense = dict(previous or {})
        for field, source in [('api_base', 'embed_base'), ('model', 'embed_model'), ('api_key', 'embed_key')]:
            dense[field] = values[source] or dense.get(field, '')
        dense['api_base'] = endpoint(dense['api_base'], 'Embedding')
        if not dense['model']:
            raise ValueError('Embedding 模型不能为空')
        try:
            dimension = int(values['embed_dimension'] or dense.get('dimension', 0))
        except (TypeError, ValueError):
            raise ValueError('Embedding 维度必须为整数') from None
        if not 1 <= dimension <= 65536:
            raise ValueError('Embedding 维度必须在 1 到 65536 之间')
        dense.update(provider='openai', dimension=dimension, input='text')
    if previous:
        for field in ('provider', 'model', 'dimension', 'model_path'):
            if previous.get(field) != dense.get(field):
                raise ValueError('禁止直接切换 Embedding 模型或维度；需要备份并重建索引')
    config.setdefault('embedding', {}).update(dense=dense, max_concurrent=1, text_source='content_only')
    config.setdefault('log', {}).update(level='INFO', output='stdout')
    return config


def apply_config(state, values, variant):
    path = state / 'openviking' / 'ov.conf'
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('配置目录不能是符号链接')
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    config = make_config(values, variant, old)
    if old:
        atomic_json(path.with_suffix('.conf.previous'), old)
    atomic_json(path, config)
    os.chmod(path.parent, 0o700)


def main():
    state = Path('/state')
    action = sys.argv[1]
    if action == 'configure':
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError('输入过长')
        parts = raw.decode('utf-8').split('\0')
        if len(parts) != len(FIELDS) + 1 or parts[-1] != '':
            raise ValueError('配置输入格式无效')
        apply_config(state, dict(zip(FIELDS, parts[:-1])), sys.argv[2])
    elif action == 'backup':
        backup_state(state)
    elif action == 'restore':
        restore_state(state, sys.argv[2])
    elif action == 'delete':
        # Only children of the explicitly mounted application state can be removed.
        for name in ('openviking', 'models'):
            target = state / name
            if target.is_symlink():
                raise ValueError('拒绝删除符号链接目录')
            if target.exists():
                shutil.rmtree(target)
    else:
        raise ValueError('未知操作')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print user-controlled values or exception reprs containing secrets.
        print('配置操作失败：请检查输入字段、目录权限及现有索引兼容性。', file=sys.stderr)
        sys.exit(1)
