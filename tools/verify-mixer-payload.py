#!/usr/bin/env python3
"""Reject an incomplete or mismatched native mixer release payload."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(payload, lock):
    mixer = lock['components']['mixer']
    inputs = mixer['build_inputs']
    app = Path(payload)/'usr/lib/oscmix-ufxplus'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    source = json.loads((app/'source.json').read_text())
    if source['source_head'] != mixer['commit'] or not source['working_tree_clean']:
        raise ValueError('Mixer source differs from the pinned clean commit')
    manifest_path = app/'rme-runtime/manifest.json'
    if digest(manifest_path) != inputs['runtime_manifest_sha256']:
        raise ValueError('Native runtime manifest differs from the pinned input')
    manifest = json.loads(manifest_path.read_text())
    if manifest['source_head'] != inputs['runtime_source_commit']:
        raise ValueError('Native runtime source differs')
    if any(manifest.get(name) != 1 for name in ('linux_host_abi', 'linux_settings_abi', 'linux_rate_abi')):
        raise ValueError('Native runtime ABI is incomplete')
    required = {'auto.py', 'launch.py', 'rate_change.py', 'rme-control-layout',
                'rme-live-audio', 'rme-midi', 'ufxplusctl'}
    if not required.issubset(manifest['files']):
        raise ValueError('Native runtime payload is incomplete')
    for name, expected in manifest['files'].items():
        path = app/'rme-runtime'/name
        if Path(name).name != name or path.is_symlink() or digest(path) != expected:
            raise ValueError('Native runtime input differs: '+name)
    if digest(app/'bin/rme-live-levels') != inputs['control_sha256']:
        raise ValueError('Mixer control producer differs from the pinned input')
    if not (Path(payload)/'usr/lib/systemd/user/rme-native-devices.service').is_file():
        raise ValueError('Native device service is missing')
    print('Pinned mixer source, native runtime and control producer verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    parser.add_argument('lock', type=Path)
    args = parser.parse_args()
    verify(args.payload, json.loads(args.lock.read_text()))
