"""Stage existing public bytes without Jekyll or data transformation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Output must not exist; refuse to overwrite files')
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(['git', 'status', '--porcelain', '--', 'index.html', 'assets', 'data'], cwd=ROOT, text=True)
    if changed.strip():
        raise ValueError('Public snapshot has uncommitted changes')
    files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'index.html', 'assets', 'data'], cwd=ROOT).decode().split('\0')
    output.mkdir(parents=True)
    hashes = {}
    for name in filter(None, files):
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Only regular tracked public files allowed: {name}')
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f'Copy mismatch: {name}')
    if 'index.html' not in hashes:
        raise ValueError('Missing index.html')
    (output / '.nojekyll').touch()
    (output / 'deployment-version.json').write_text(json.dumps({'commit': sha, 'files': hashes}, sort_keys=True), encoding='utf-8')
    print(f'Staged {len(hashes)} unchanged public files from {sha}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    build(parser.parse_args().output)
