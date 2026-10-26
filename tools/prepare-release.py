#!/usr/bin/env python3
"""Stage both tested archives and one checksum file for a single release."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def checked_archive(path):
    with tarfile.open(path) as archive:
        files = {}
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or name.parts[0] != 'ufxplus-linux-suite':
                raise ValueError('Unsafe archive member')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Unexpected archive link or device')
            relative = str(name.relative_to('ufxplus-linux-suite'))
            if relative in files:
                raise ValueError('Duplicate archive member')
            files[relative] = archive.extractfile(member).read()
        listed = set()
        for line in files['SHA256SUMS'].decode().splitlines():
            expected, name = line.split('  ', 1)
            name = name.removeprefix('./')
            if name in listed or hashlib.sha256(files[name]).hexdigest() != expected:
                raise ValueError('Archive checksum mismatch: '+name)
            listed.add(name)
        if listed != set(files)-{'SHA256SUMS'}:
            raise ValueError('Archive contains unchecked files')
        return files


def prepare(directory, tag, expected, commit):
    version = expected['suite']['version']
    if tag != 'v'+version:
        raise ValueError('Tag must match components.lock.json: v'+version)
    patterns = ('mint/*_amd64.tar.gz', 'fedora/*_fedora44_x86_64.tar.gz')
    archives = []
    for pattern in patterns:
        candidates = list(directory.glob(pattern))
        if len(candidates) != 1:
            raise ValueError('Exactly one archive is required for each distribution')
        path = candidates[0]
        files = checked_archive(path)
        if json.loads(files['components.lock.json']) != expected:
            raise ValueError('The two archives must use the current pinned components')
        if 'fedora-manifest.json' in files:
            manifest = json.loads(files['fedora-manifest.json'])
            if manifest['suite_version'] != version or manifest['adapter_commit'] != commit:
                raise ValueError('Fedora archive comes from another version or commit')
        elif files['metadata/source-commit'].decode().strip() != commit:
            raise ValueError('Mint archive comes from another commit')
        archives.append(path)
    upload = directory/'upload'
    upload.mkdir(exist_ok=False)
    for path in archives:
        shutil.copy2(path, upload/path.name)
    (upload/'SHA256SUMS').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(upload.glob('*.tar.gz'))))
    print('Both distribution archives verified for '+tag+' at '+commit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    prepare(args.directory, args.tag, json.loads((ROOT/'components.lock.json').read_text()),
            subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
