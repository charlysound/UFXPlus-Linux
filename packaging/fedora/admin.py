#!/usr/bin/python3
"""Explicit native ALSA module preparation; never start desktop audio as root."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess

def prepare(kernel=None,no_load=False):
    if os.geteuid()!=0:raise ValueError('Kernel preparation requires administrator authentication')
    source=Path('/usr/src/rme-pcm-0.1.0')
    hashes=json.loads(Path('/usr/share/ufxplus-linux/fedora-module.json').read_text())
    for name,expected in hashes.items():
        path=source/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Installed kernel source changed: '+name)
    kernel=kernel or platform.release()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{1,127}',kernel):raise ValueError('Invalid kernel release')
    if kernel!=platform.release() and not no_load:raise ValueError('Use --no-load when preparing a different installed kernel')
    if not (Path('/lib/modules')/kernel/'build/Makefile').is_file():
        raise ValueError('Missing exact kernel-devel build tree for '+kernel+'; install the matching package from the kernel provider before activation')
    result=subprocess.run(['dkms','status','-m','rme-pcm','-v','0.1.0'],capture_output=True,text=True,check=True)
    if not result.stdout.strip():subprocess.run(['dkms','add','-m','rme-pcm','-v','0.1.0'],check=True)
    subprocess.run(['dkms','build','--force','-m','rme-pcm','-v','0.1.0','-k',kernel],check=True)
    subprocess.run(['dkms','install','--force','-m','rme-pcm','-v','0.1.0','-k',kernel],check=True)
    subprocess.run(['dracut','--force','--kver',kernel],check=True)
    if not no_load:subprocess.run(['modprobe','snd-rme-pcm'],check=True)
    subprocess.run(['udevadm','control','--reload-rules'],check=True)
    print('Native ALSA module built'+('' if no_load else ' and loaded')+' for '+kernel)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--kernel');parser.add_argument('--no-load',action='store_true');args=parser.parse_args()
    try:prepare(args.kernel,args.no_load)
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise SystemExit('RME Fedora kernel setup: '+str(error))
