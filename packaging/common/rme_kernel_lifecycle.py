"""Model-independent guards shared by DEB hooks and the Fedora adapter."""
import argparse
import os
from pathlib import Path
import re
import subprocess

DIRECTIVE_KEY = 'DKMS_DIRECTIVE_RME'
DIRECTIVE_VALUE = 'post_transaction=/usr/bin/true'
PROC = Path('/proc')
SYS_MODULE = Path('/sys/module/snd_rme_pcm')
BOOT = Path('/boot')


def dkms_environment():
    version = subprocess.check_output(['dkms', '--version'], text=True).strip()
    match = re.fullmatch(r'dkms-3\.(\d+)\.\d+(?:[-+].*)?', version)
    if not match or not 0 <= int(match.group(1)) < 5:
        raise ValueError('Unsupported DKMS version for isolated operations: ' + version)
    env = {key: value for key, value in os.environ.items() if not key.startswith('DKMS_DIRECTIVE')}
    env[DIRECTIVE_KEY] = DIRECTIVE_VALUE
    return env


def require_idle(proc=PROC, sys_module=SYS_MODULE):
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            args = (process / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        if any(arg in (
            b'/usr/lib/oscmix-ufxplus/rme-runtime/auto.py',
            b'/usr/lib/oscmix-ufxplus/rme-runtime/launch.py',
            b'/usr/share/ufxplus-driver/service_start.py',
        ) for arg in args):
            raise ValueError('Stop the RME user services before changing the kernel module')
    if sys_module.exists() and int((sys_module / 'refcnt').read_text().strip()) != 0:
        raise ValueError('The RME kernel module is in use; stop audio first')


def remove_dkms():
    if os.geteuid() != 0:
        raise ValueError('Kernel removal requires administrator authentication')
    require_idle()
    env = dkms_environment()
    status = subprocess.check_output(['dkms', 'status', '-m', 'rme-pcm', '-v', '0.1.0'], text=True, env=env)
    for line in status.splitlines():
        fields = line.split(',')
        if len(fields) < 3:
            continue
        kernel = fields[1].strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{1,127}', kernel):
            raise ValueError('Invalid registered kernel release')
        image = BOOT / ('initrd.img-' + kernel)
        if image.is_file():
            listing = subprocess.check_output(['lsinitramfs', str(image)], text=True)
            if re.search(r'/snd[-_]rme[-_]pcm\.ko(?:\.|$)', listing, re.M):
                raise ValueError('RME module remains in ' + str(image) + '; migrate that image before removal; package sources retained')
    if SYS_MODULE.exists():
        subprocess.run(['modprobe', '-r', 'snd-rme-pcm'], check=True)
    if status.strip():
        subprocess.run(['dkms', 'remove', '-m', 'rme-pcm', '-v', '0.1.0', '--all'], env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check-idle', action='store_true')
    group.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    try:
        if args.check_idle:
            require_idle()
        else:
            remove_dkms()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit('RME kernel lifecycle: ' + str(error))


if __name__ == '__main__':
    main()
