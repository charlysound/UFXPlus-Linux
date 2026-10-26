#!/usr/bin/python3
"""Real dpkg transactions in a disposable Mint CI container, with fake DKMS.

The fake compiler/remover proves hook ordering and failure propagation. It does
not load modules, access hardware, or qualify the running container kernel.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0 or not Path('/.dockerenv').exists():
        raise SystemExit('Run only as root in a disposable Docker CI container')
    packages = {subprocess.check_output(['dpkg-deb', '-f', str(p), 'Package'], text=True).strip(): str(p.resolve())
                for p in args.packages.glob('*.deb')}
    if set(packages) != {'ufxplus-driver', 'rme-native-host', 'oscmix-ufxplus'}:
        raise SystemExit('Expected the three pinned DEBs')
    for name in packages:
        result = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', name], capture_output=True, text=True)
        if result.stdout == 'installed':
            raise SystemExit('The disposable container already has RME packages')
    with tempfile.TemporaryDirectory(prefix='rme-deb-lifecycle-') as temporary:
        work = Path(temporary)
        fake = work/'bin'; fake.mkdir()
        dkms = fake/'dkms'
        dkms.write_text('''#!/bin/sh
set -eu
case "$*" in
  --version) echo dkms-3.0.11; exit 0 ;;
  *ufxplus-pcm*) exit 0 ;;
esac
printf '%s\\n' "$*" >> "$RME_PROBE/calls"
case "$1" in
  status) if [ -f "$RME_PROBE/registered" ]; then echo 'rme-pcm/0.1.0, fixture-kernel, x86_64: installed'; fi ;;
  add) touch "$RME_PROBE/registered" ;;
  build|install) test "$DKMS_DIRECTIVE_RME" = post_transaction=/usr/bin/true ;;
  remove)
    test -f /usr/src/rme-pcm-0.1.0/dkms.conf
    test "$DKMS_DIRECTIVE_RME" = post_transaction=/usr/bin/true
    if [ -f "$RME_PROBE/deny" ]; then exit 23; fi
    rm -f "$RME_PROBE/registered"
    ;;
  *) exit 99 ;;
esac
''')
        dkms.chmod(0o755)
        env = dict(os.environ, PATH=str(fake)+':'+os.environ['PATH'], RME_PROBE=str(work))

        def dpkg(*command, ok=True):
            result = subprocess.run(['dpkg', *command], env=env, capture_output=True, text=True)
            print(result.stdout, end=''); print(result.stderr, end='')
            if ok and result.returncode:
                raise RuntimeError('dpkg failed: '+str(command))
            return result

        # Keep the legacy driver installed to verify restoration of diversions.
        dpkg('--force-depends', '-i', packages['ufxplus-driver'])
        legacy = Path('/usr/bin/ufxplus-driver-panel')
        original = hashlib.sha256(legacy.read_bytes()).hexdigest()
        sentinel = Path('/root/.config/oscmix/joint-release-sentinel')
        sentinel.parent.mkdir(parents=True, exist_ok=True); sentinel.write_text('keep settings\n')
        dpkg('--force-depends', '-i', packages['rme-native-host'], packages['oscmix-ufxplus'])
        assert (work/'registered').is_file()
        (work/'calls').write_text('')
        dpkg('--force-depends', '-i', packages['rme-native-host'])
        assert not any(line.startswith('remove ') for line in (work/'calls').read_text().splitlines())
        (work/'deny').touch()
        denied = dpkg('--force-depends', '-r', 'rme-native-host', ok=False)
        assert denied.returncode != 0, 'Failed DKMS removal must block package removal'
        assert Path('/usr/src/rme-pcm-0.1.0/dkms.conf').is_file(), 'Source was deleted before cleanup'
        (work/'deny').unlink()
        dpkg('--force-depends', '-r', 'rme-native-host')
        assert not (work/'registered').exists()
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == original
        dpkg('--force-depends', '-r', 'oscmix-ufxplus', 'ufxplus-driver')
        assert sentinel.read_text() == 'keep settings\n'
        assert not Path('/usr/src/rme-pcm-0.1.0/dkms.conf').exists()
        print(json.dumps(dict(environment='Mint container; real dpkg, fake DKMS', install='pass',
                              upgrade_preserves_registration='pass', failed_removal_preserves_sources='pass',
                              removal='pass', diversions_restored='pass', settings_preserved='pass'), indent=2))


if __name__ == '__main__':
    main()
