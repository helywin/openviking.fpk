"""Run as root on the test NAS after uploading the test FPK. No secret output."""
import os
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

folder = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fpk', type=Path, default=folder / 'openviking-local.fpk')
parser.add_argument('--existing-config', type=Path)
parser.add_argument('--local-directory', type=Path, help='Use official install-local for an unpacked package')
args = parser.parse_args()
root_key = (json.loads(args.existing_config.read_text())['server']['root_api_key']
            if args.existing_config else secrets.token_urlsafe(32))
if not re.fullmatch(r'[A-Za-z0-9_-]{24,}', root_key):
    raise ValueError('Test installer requires a token-safe key; use the GUI for other key formats')
fd, filename = tempfile.mkstemp(prefix='install-', suffix='.env', dir=folder)
try:
    with os.fdopen(fd, 'w') as stream:
        stream.write('wizard_root_key=' + root_key + '\n')
    command = (['appcenter-cli', 'install-local', '--dir', str(args.local_directory)]
               if args.local_directory else ['appcenter-cli', 'install-fpk', str(args.fpk)])
    result = subprocess.run(command + ['--env', filename, '-v', '1'])
    raise SystemExit(result.returncode)
finally:
    os.unlink(filename)
