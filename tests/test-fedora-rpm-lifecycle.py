#!/usr/bin/python3
"""Exercise real RPM install/upgrade/removal hooks in a temporary chroot.

The kernel helper is replaced by an inert probe inside the fixture: this checks
RPM lifecycle dispatch and failure propagation, not real DKMS or hardware.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Run the isolated RPM transaction fixture as root')
    packages=[str(p.resolve()) for p in sorted(args.packages.glob('*.rpm'))]
    if len(packages)!=3:raise SystemExit('Expected the three candidate RPMs')
    with tempfile.TemporaryDirectory(prefix='rme-rpm-lifecycle-') as directory:
        root=Path(directory)
        for name in ('bin','usr/bin','dev','probe'):(root/name).mkdir(parents=True,exist_ok=True)
        shutil.copy2('/bin/sh',root/'bin/sh',follow_symlinks=True)
        libs=subprocess.check_output(['ldd','/bin/sh'],text=True)
        for name in set(re.findall(r'/[^\s()]+',libs)):
            path=Path(name)
            if path.is_file():
                target=root/name.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target,follow_symlinks=True)
        (root/'dev/null').touch()
        udev=root/'usr/bin/udevadm';udev.write_text('#!/bin/sh\nexit 0\n');udev.chmod(0o755)
        def rpm(*command,ok=True):
            result=subprocess.run(['rpm','--root',str(root),*command],capture_output=True,text=True)
            if ok and result.returncode:raise RuntimeError(result.stdout+result.stderr)
            return result
        rpm('--initdb')
        rpm('-i','--nodeps',*packages)
        helper=root/'usr/libexec/ufxplus-linux/fedora-admin'
        probe='#!/bin/sh\nprintf "%s" "$*" > /probe/called\nexit 23\n'
        helper.write_text(probe);helper.chmod(0o755)
        # The final-removal hook must not run during an upgrade.
        rpm('-U','--nodeps','--replacepkgs',*packages)
        if (root/'probe/called').exists():raise AssertionError('Upgrade ran removal hook')
        helper.write_text(probe);helper.chmod(0o755)
        denied=rpm('-e','--nodeps','rme-native-host',ok=False)
        if denied.returncode==0:raise AssertionError('Busy removal was accepted')
        rpm('-q','rme-native-host')
        if (root/'probe/called').read_text()!='--remove':raise AssertionError('Wrong removal helper arguments')
        helper.write_text('#!/bin/sh\nprintf "%s" "$*" > /probe/called\nexit 0\n');helper.chmod(0o755)
        rpm('-e','--nodeps','rme-native-host')
        if rpm('-q','rme-native-host',ok=False).returncode==0:raise AssertionError('Package remained installed')
        print(json.dumps(dict(fixture='temporary chroot; inert kernel helper',install='pass',upgrade_preserves_dkms='pass',busy_removal_refused='pass',final_removal='pass'),indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
