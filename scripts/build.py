"""Build test FPKs with the official fnpack; requires Python 3.10+."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build(args):
    tool = Path(args.fnpack).resolve()
    if not tool.is_file():
        raise ValueError('fnpack executable not found')
    if args.variant == 'local':
        pinned = args.image and re.fullmatch(r'[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}', args.image)
        preloaded = (args.preloaded_image or args.image_archive) and args.image and re.fullmatch(r'sha256:[a-f0-9]{64}', args.image)
        if not (pinned or preloaded):
            raise ValueError('Local image must be published and pinned by SHA-256 digest')
        if not args.model or not args.model_sha256:
            raise ValueError('Local package requires --model and --model-sha256')
        if sha256(Path(args.model)) != args.model_sha256:
            raise ValueError('Model SHA-256 mismatch')
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    scratch = ROOT / '.build'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fpk-', dir=scratch) as directory:
        stage = Path(directory) / 'package'
        shutil.copytree(ROOT / 'openviking', stage,
                        ignore=shutil.ignore_patterns('.DS_Store', '__pycache__', '*.pyc'))
        # Preserve old installations without moving their private workspace.
        appname = args.app_id
        for path in [stage / 'manifest', stage / 'config/resource', stage / 'config/privilege', stage / 'app/ui/config']:
            content = path.read_text(encoding='utf-8')
            if path.name == 'manifest':
                content = re.sub(r'(?m)^appname\s*=.*$', 'appname = ' + appname, content)
                content = re.sub(r'(?m)^desktop_applaunchname\s*=.*$', 'desktop_applaunchname = ' + appname + '.main', content)
                content = re.sub(r'(?m)^version\s*=.*$', 'version = ' + args.version, content)
                content = re.sub(r'(?m)^platform\s*=.*$', 'platform = ' + ('arm' if args.arch == 'arm64' else 'x86'), content)
                if args.variant == 'local':
                    content = re.sub(r'(?m)^desc\s*=.*$', 'desc = OpenViking 纯文本本地 BGE Embedding，无需外部模型 API。测试版。', content)
            if path == stage / 'app/ui/config':
                config = json.loads(content)
                config['.url'] = {appname + '.main': config['.url']['openviking.main']}
                content = json.dumps(config, ensure_ascii=False, indent=2) + '\n'
            path.write_text(content, encoding='utf-8', newline='\n')
        if args.variant == 'local':
            if args.arch != 'arm64':
                raise ValueError('Local variant currently targets arm64 only')
            # fnOS docker-project pulls before upgrade_callback. Offline images
            # must instead be loaded before the app's own Compose start.
            # Keep data-share declarations; Compose is managed by cmd/main.
            settings = stage / 'app/settings.json'
            old_image = json.loads(settings.read_text())['image']
            settings_value = dict(variant='local', image=args.image)
            if args.image_archive:
                archive_path = Path(args.image_archive)
                with tarfile.open(archive_path) as archive:
                    manifest = json.load(archive.extractfile('manifest.json'))
                    if len(manifest) != 1:
                        raise ValueError('Bundle must contain exactly one image')
                    config_bytes = archive.extractfile(manifest[0]['Config']).read()
                    if 'sha256:' + hashlib.sha256(config_bytes).hexdigest() != args.image:
                        raise ValueError('Bundled image does not match --image ID')
                settings_value['image_archive_sha256'] = sha256(archive_path)
                shutil.copyfile(archive_path, stage / 'app/runtime-image.tar')
            settings.write_text(json.dumps(settings_value, indent=2) + '\n')
            compose = stage / 'app/docker/docker-compose.yaml'
            content = compose.read_text().replace(old_image, args.image)
            compose.write_text(content, newline='\n')
            models = stage / 'app/models'
            models.mkdir()
            filename = 'bge-small-zh-v1.5-f16.gguf'
            shutil.copyfile(args.model, models / filename)
            (models / 'SHA256SUMS').write_text(args.model_sha256 + '  ' + filename + '\n')
            for name in ('install', 'config'):
                wizard = stage / 'wizard' / name
                pages = json.loads(wizard.read_text(encoding='utf-8'))
                for page in pages:
                    page['items'] = [item for item in page['items'] if not item.get('field', '').startswith('wizard_embed_')]
                    page['items'].append({'type': 'tips', 'helpText': 'Embedding 固定为本地 BGE 512 维文本模型，使用 CPU。无需外部 API；未启用生成式摘要和图片理解。'})
                wizard.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding='utf-8')
        if appname == 'openviking-local':
            compose = stage / 'app/docker/docker-compose.yaml'
            compose.write_text(compose.read_text().replace('openviking-fnos', 'openviking-fnos-local'), newline='\n')
        for path in stage.rglob('*'):
            if path.is_file() and path.suffix.lower() not in ('.png', '.gguf', '.tar'):
                content = path.read_text(encoding='utf-8')
                path.write_text(content, encoding='utf-8', newline='\n')
            if path.is_file() and path.parent.name == 'cmd':
                path.chmod(0o755)
        if args.container_build:
            subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                            '--mount', f'type=bind,src={stage},dst=/input,readonly',
                            '--mount', f'type=bind,src={stage},dst=/output',
                            '--mount', f'type=bind,src={tool},dst=/tool,readonly',
                            '--entrypoint', 'bash',
                            'ghcr.io/volcengine/openviking:v0.4.16@sha256:46f9e34cd37238c28cbd9535033773d179006bdf7f3e528dd1c46567abce7701',
                            '-c', 'set -eu; cp -a /input /tmp/package; cp /tool /tmp/fnpack; chmod 755 /tmp/fnpack /tmp/package/cmd/*; cd /tmp/package; /tmp/fnpack build; cp *.fpk /output/'], check=True)
        else:
            subprocess.run([str(tool), 'build'], cwd=stage, check=True)
        packages = list(stage.glob('*.fpk'))
        if len(packages) != 1:
            raise ValueError('Expected one FPK')
        dest = output / f'{appname}-{args.variant}-{args.version}-{args.arch}-test.fpk'
        shutil.copyfile(packages[0], dest)
        with tarfile.open(dest, 'r:*') as archive:
            if not any(n.rstrip('/') == 'manifest' for n in archive.getnames()):
                raise ValueError('Missing manifest in FPK')
            if any('.DS_Store' in n for n in archive.getnames()):
                raise ValueError('Unexpected macOS metadata')
            if any(m.isfile() and m.name.startswith('cmd/') and not m.mode & 0o111 for m in archive):
                raise ValueError('Lifecycle scripts are not executable. On Windows use --container-build with Linux fnpack.')
        (dest.with_suffix('.fpk.sha256')).write_text(sha256(dest) + '  ' + dest.name + '\n')
        metadata = dict(app_id=appname, variant=args.variant, arch=args.arch, acceptance='not-tested-on-fnos',
                        fnpack_sha256=sha256(tool), fpk_sha256=sha256(dest),
                        image=json.loads((stage / 'app/settings.json').read_text())['image'],
                        model_sha256=args.model_sha256, preloaded_image=args.preloaded_image,
                        bundled_image=bool(args.image_archive), version=args.version)
        dest.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print(dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fnpack', default=str(ROOT / '.tools/fnpack.exe'))
    parser.add_argument('--variant', choices=['standard', 'local'], default='standard')
    parser.add_argument('--app-id', choices=['openviking', 'openviking-local'], default='openviking',
                        help='Use openviking-local only to upgrade an existing legacy installation without migrating data')
    parser.add_argument('--container-build', action='store_true', help='Run Linux amd64 fnpack in Docker to preserve executable bits on Windows')
    parser.add_argument('--arch', choices=['amd64', 'arm64'], default='amd64')
    parser.add_argument('--image')
    parser.add_argument('--version', default='0.4.16-9', type=lambda v: v if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+-[0-9]+', v) else parser.error('Invalid package version'))
    parser.add_argument('--image-archive', help='Bundle a docker save archive matching the exact --image ID; no registry is needed at install time')
    parser.add_argument('--preloaded-image', action='store_true', help='Test package only: use an exact image ID already loaded on the target NAS')
    parser.add_argument('--model')
    parser.add_argument('--model-sha256')
    build(parser.parse_args())
