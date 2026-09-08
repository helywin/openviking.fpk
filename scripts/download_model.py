"""Download the pinned BGE model to ignored build storage and verify its SHA-256."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
NAME = 'bge-small-zh-v1.5-f16.gguf'
URL = 'https://huggingface.co/CompendiumLabs/bge-small-zh-v1.5-gguf/resolve/main/' + NAME
SHA256 = 'ab9b81d9cd329c712eee379cf0068eabe6a5e2a01d0def61535eba9384085e2c'
SIZE = 47886240


def download():
    target = ROOT / '.build/models' / NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        return target
    temporary = target.with_suffix('.part')
    try:
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open('wb') as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                size += len(chunk)
                if size > SIZE:
                    raise ValueError('Unexpected model size')
                digest.update(chunk)
                output.write(chunk)
        if size != SIZE or digest.hexdigest() != SHA256:
            raise ValueError('Model integrity check failed')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    print(download())
