#!/usr/bin/python3
"""Prepare or retire the desktop RME module without rebuilding unrelated boots."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

SOURCE = Path('/usr/src/rme-pcm-0.1.0')
MODULES = Path('/lib/modules')
BOOT = Path('/boot')
SYS_MODULE = Path('/sys/module/snd_rme_pcm')
PROC = Path('/proc')
HASHES = Path('/usr/share/ufxplus-linux/fedora-module.json')
MODULE = 'snd-rme-pcm'


def validate_kernel(kernel):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{1,127}', kernel):
        raise ValueError('Invalid kernel release')
    return kernel


def dkms_env():
    """DKMS 3.4 safe_source applies overrides after each config read.

    Keep signing and administrator settings; disable only the per-process
    post-transaction command, without editing the host framework configuration.
    """
    version = subprocess.check_output(['dkms', '--version'], text=True).strip()
    if not re.fullmatch(r'dkms-3\.4\.\d+(?:[-+].*)?', version):
        raise ValueError('Unsupported DKMS version for isolated operations: ' + version)
    env = {k: v for k, v in os.environ.items() if not k.startswith('DKMS_DIRECTIVE')}
    env['DKMS_DIRECTIVE_RME'] = 'post_transaction=/usr/bin/true'
    return env


def dkms(args, env):
    return subprocess.run(['dkms', *args], env=env, check=True)


def require_idle():
    for process in PROC.iterdir():
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
    if SYS_MODULE.exists() and int((SYS_MODULE / 'refcnt').read_text().strip()) != 0:
        raise ValueError('The RME kernel module is in use; stop audio first')


def image_modules(image):
    listing = subprocess.check_output(['lsinitrd', str(image)], text=True)
    return set(re.findall(r'\b(?:usr/)?lib/modules/[^\s]+?\.ko(?:\.(?:xz|gz|zst))?(?=\s|$)', listing))


def is_rme_module(name):
    return re.search(r'/snd[-_]rme[-_]pcm\.ko(?:\.|$)', name) is not None


def clean_image(kernel):
    """Only migrate images already containing this desktop-only module.

    Reject masked dracut errors and missing unrelated modules before replacing
    the old image. A failed migration leaves the old image available.
    """
    validate_kernel(kernel)
    image = BOOT / ('initramfs-' + kernel + '.img')
    if not image.is_file():
        return
    before = image_modules(image)
    if not any(map(is_rme_module, before)):
        return
    # Keep even dependencies pulled in only by the old RME module. Merely
    # omitting it lets dracut prune snd-pcm/snd-timer from an existing image.
    keep = sorted({Path(name).name.split('.ko', 1)[0] for name in before if not is_rme_module(name)})
    with tempfile.TemporaryDirectory(prefix='.rme-initramfs-', dir=BOOT) as temporary:
        candidate = Path(temporary) / image.name
        result = subprocess.run(
            ['dracut', '--force', '--kver', kernel, '--add-drivers', ' '.join(keep), '--omit-drivers', 'snd_rme_pcm',
             '--remove', '/usr/lib/modules-load.d/rme-pcm.conf', str(candidate)],
            capture_output=True, text=True)
        output = result.stdout + result.stderr
        if result.returncode or re.search(r'dracut\[(?:E|F)\]|Failed to find module|FAILED:', output):
            raise ValueError('Target initramfs rebuild failed; original preserved: ' + output[-4000:])
        after = image_modules(candidate)
        missing = {name for name in before - after if not is_rme_module(name)}
        if missing or any(map(is_rme_module, after)):
            raise ValueError('Target initramfs validation failed; original preserved; missing: ' + repr(sorted(missing)))
        candidate.chmod(image.stat().st_mode & 0o777)
        subprocess.run(['chcon', '--reference=' + str(image), str(candidate)], check=True)
        with candidate.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(candidate, image)
        directory = os.open(BOOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    print('Removed desktop RME module from target initramfs: ' + kernel)


def registered_kernels(status):
    kernels = set()
    for line in status.splitlines():
        fields = line.split(',')
        if len(fields) >= 3:
            kernels.add(validate_kernel(fields[1].strip()))
    return sorted(kernels)


def prepare(kernel=None, no_load=False):
    if os.geteuid() != 0:
        raise ValueError('Kernel preparation requires administrator authentication')
    kernel = validate_kernel(kernel or platform.release())
    if kernel != platform.release() and not no_load:
        raise ValueError('Use --no-load when preparing a different installed kernel')
    if not (MODULES / kernel / 'build/Makefile').is_file():
        raise ValueError('Missing exact kernel-devel build tree for ' + kernel)
    for name, expected in json.loads(HASHES.read_text()).items():
        path = SOURCE / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Installed kernel source changed: ' + name)
    env = dkms_env()
    require_idle()
    clean_image(kernel)
    if not no_load and SYS_MODULE.exists():
        subprocess.run(['modprobe', '-r', MODULE], check=True)
    status = subprocess.check_output(['dkms', 'status', '-m', 'rme-pcm', '-v', '0.1.0'], text=True, env=env)
    if not status.strip():
        dkms(['add', '-m', 'rme-pcm', '-v', '0.1.0'], env)
    dkms(['build', '--force', '-m', 'rme-pcm', '-v', '0.1.0', '-k', kernel], env)
    dkms(['install', '--force', '-m', 'rme-pcm', '-v', '0.1.0', '-k', kernel], env)
    # modules-load.d loads the frontend after mounting the root filesystem.
    # No initramfs rebuild is needed for a fresh installation.
    if not no_load:
        subprocess.run(['modprobe', MODULE], check=True)
    subprocess.run(['udevadm', 'control', '--reload-rules'], check=True)
    print('Native ALSA module built' + ('' if no_load else ' and loaded') + ' for ' + kernel)


def remove():
    if os.geteuid() != 0:
        raise ValueError('Kernel removal requires administrator authentication')
    env = dkms_env()
    require_idle()
    status = subprocess.check_output(['dkms', 'status', '-m', 'rme-pcm', '-v', '0.1.0'], text=True, env=env)
    for kernel in registered_kernels(status):
        clean_image(kernel)
    if SYS_MODULE.exists():
        subprocess.run(['modprobe', '-r', MODULE], check=True)
    if status.strip():
        dkms(['remove', '-m', 'rme-pcm', '-v', '0.1.0', '--all'], env)
    print('RME DKMS registration and installed modules removed; user settings preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel')
    parser.add_argument('--no-load', action='store_true')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    try:
        if args.remove:
            if args.kernel or args.no_load:
                raise ValueError('--remove cannot be combined with preparation options')
            remove()
        else:
            prepare(args.kernel, args.no_load)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('RME Fedora kernel setup: ' + str(error))
