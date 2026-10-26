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
    parser.add_argument('--previous',type=Path,help='Previous release RPMs for a real version upgrade')
    args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('Run the isolated RPM transaction fixture as root')
    packages=[str(p.resolve()) for p in sorted(args.packages.glob('*.rpm'))]
    if len(packages)!=3:raise SystemExit('Expected the three candidate RPMs')
    with tempfile.TemporaryDirectory(prefix='rme-rpm-lifecycle-') as directory:
        root=Path(directory)
        root.chmod(0o755)
        for name in ('bin','usr/bin','usr/lib/sysimage/rpm','dev','var/lib/rpm-state/rme-probe'):(root/name).mkdir(parents=True,exist_ok=True)
        shutil.copy2('/bin/sh',root/'bin/sh',follow_symlinks=True)
        libs=subprocess.check_output(['ldd','/bin/sh'],text=True)
        for name in set(re.findall(r'/[^\s()]+',libs)):
            path=Path(name)
            if path.is_file():
                target=root/name.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target,follow_symlinks=True)
        (root/'dev/null').touch()
        udev=root/'usr/bin/udevadm';udev.write_text('#!/bin/sh\nexit 0\n');udev.chmod(0o755)
        contexts=Path('/etc/selinux/targeted/contexts/files/file_contexts')
        if shutil.which('selinuxenabled') and subprocess.run(['selinuxenabled']).returncode==0:
            if not contexts.is_file():raise RuntimeError('SELinux is enabled but its file contexts are unavailable')
            # A chroot under /tmp otherwise inherits temporary-file labels;
            # RPM's confined database writer cannot use those labels.
            subprocess.run(['setfiles','-r',str(root),str(contexts),str(root)],check=True)
        def rpm(*command,ok=True):
            # The fixture checks scriptlet dispatch, not host integration
            # plugins (SELinux, systemd inhibition, audit, ...).
            result=subprocess.run(['rpm','--noplugins','--root',str(root),*command],capture_output=True,text=True)
            if ok and result.returncode:raise RuntimeError(result.stdout+result.stderr)
            return result
        rpm('--initdb')
        previous=[str(p.resolve()) for p in sorted(args.previous.glob('*.rpm'))] if args.previous else packages
        if len(previous)!=3:raise ValueError('Expected three previous RPMs')
        rpm('-i','--nodeps',*previous)
        helper=root/'usr/libexec/ufxplus-linux/fedora-admin'
        probe='#!/bin/sh\nprintf "%s" "$*" > /var/lib/rpm-state/rme-probe/called\nexit 23\n'
        helper.write_text(probe);helper.chmod(0o755)
        # The final-removal hook must not run during an upgrade.
        rpm('-U','--nodeps','--replacepkgs',*packages)
        if (root/'var/lib/rpm-state/rme-probe/called').exists():raise AssertionError('Upgrade ran removal hook')
        helper.write_text(probe);helper.chmod(0o755)
        denied=rpm('-e','--nodeps','rme-native-host',ok=False)
        if denied.returncode==0:raise AssertionError('Busy removal was accepted')
        rpm('-q','rme-native-host')
        if (root/'var/lib/rpm-state/rme-probe/called').read_text()!='--remove':raise AssertionError('Wrong removal helper arguments')
        helper.write_text('#!/bin/sh\nprintf "%s" "$*" > /var/lib/rpm-state/rme-probe/called\nexit 0\n');helper.chmod(0o755)
        rpm('-e','--nodeps','rme-native-host')
        if rpm('-q','rme-native-host',ok=False).returncode==0:raise AssertionError('Package remained installed')
        print(json.dumps(dict(fixture='temporary chroot; inert kernel helper',install='pass',upgrade_preserves_dkms='pass',busy_removal_refused='pass',final_removal='pass'),indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
