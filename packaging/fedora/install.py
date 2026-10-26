#!/usr/bin/python3
"""Verify and install the pinned Fedora RPM suite in one DNF transaction."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
UNITS=('ufxplus-driver.service','ufxplus-midi.service','rme-native-devices.service','oscmix-with-driver.service')

def verify(root=ROOT):
    root=Path(root);manifest=json.loads((root/'fedora-manifest.json').read_text())
    if manifest.get('schema')!=1 or manifest.get('target')!=dict(id='fedora',version_id='44',architecture='x86_64'):
        raise ValueError('Invalid Fedora manifest')
    if set(manifest.get('packages',{}))!={'driver','host','mixer'}:raise ValueError('Three pinned components are required')
    for line in (root/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid checksum path')
        path=root/relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Suite checksum mismatch: '+name)
    for package in manifest['packages'].values():
        filename=Path(package['file'])
        if filename.name!=str(filename) or filename.suffix!='.rpm':raise ValueError('Invalid RPM filename')
        path=root/'packages'/filename
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=package['sha256']:raise ValueError('RPM differs from manifest: '+str(filename))
        actual=subprocess.check_output(['rpm','-qp','--qf','%{NAME}\t%{VERSION}\t%{RELEASE}\t%{ARCH}',str(path)],text=True).split('\t')
        if actual!=[package[k] for k in ('name','version','release','architecture')]:raise ValueError('RPM identity mismatch: '+str(filename))
    return manifest

def preflight(manifest):
    data={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key,value=line.split('=',1);data[key]=value.strip('"\'')
    if (data.get('ID'),data.get('VERSION_ID'),platform.machine())!=('fedora','44','x86_64'):
        raise ValueError('This bundle requires Fedora44 x86_64')
    for tool in ('rpm','dnf','sudo','systemctl'):
        if not shutil.which(tool):raise ValueError('Missing runtime installation tool: '+tool)
    return Path('/lib/modules')/platform.release()/'build/Makefile'

def backup():
    home=Path.home();state=Path(os.environ.get('XDG_STATE_HOME',home/'.local/state'))
    directory=state/'ufxplus-linux/backups';directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
    archive=directory/('fedora-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'.tar.gz')
    roots=[('XDG_CONFIG_HOME',Path(os.environ.get('XDG_CONFIG_HOME',home/'.config')),'ufxplus-driver'),('XDG_CONFIG_HOME',Path(os.environ.get('XDG_CONFIG_HOME',home/'.config')),'oscmix'),('XDG_STATE_HOME',state,'oscmix'),('XDG_DATA_HOME',Path(os.environ.get('XDG_DATA_HOME',home/'.local/share')),'oscmix')]
    with tarfile.open(archive,'w:gz') as output:
        for variable,base,name in roots:
            if not base.is_absolute():raise ValueError('XDG roots must be absolute')
            path=base/name
            if path.exists() or path.is_symlink():output.add(path,arcname=variable+'/'+name)
    archive.chmod(0o600);return archive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    for option in ('verify-only','preflight-only','backup-only','uninstall'):group.add_argument('--'+option,action='store_true')
    parser.add_argument('--allow-downgrade',action='store_true')
    args=parser.parse_args()
    if args.backup_only:print(backup());return 0
    manifest=verify()
    if args.verify_only:print('Fedora RPM identities and all suite checksums are valid.');return 0
    build=preflight(manifest)
    if args.preflight_only:
        print(json.dumps(dict(platform='Fedora44 x86_64',kernel=platform.release(),kernel_build_tree_present=build.is_file(),kernel_module_required_for_audio=True)));return 0
    if os.geteuid()==0:raise ValueError('Run as the desktop user; administrator authentication is requested for DNF')
    for unit in UNITS:
        if subprocess.run(['systemctl','--user','is-active','--quiet',unit],stderr=subprocess.DEVNULL).returncode==0:
            raise ValueError(unit+' is active; stop audio before upgrading')
    if args.uninstall:
        saved=backup();print('Settings backup: '+str(saved),flush=True)
        subprocess.run(['sudo','/usr/bin/dnf','remove','-y',*[p['name'] for p in manifest['packages'].values()]],check=True)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        print('Suite removed. Settings preserved; final host removal cleaned its DKMS registrations.')
        return 0
    if not args.allow_downgrade:
        import rpm
        for package in manifest['packages'].values():
            current=subprocess.run(['rpm','-q','--qf','%{EPOCHNUM}\t%{VERSION}\t%{RELEASE}',package['name']],capture_output=True,text=True)
            if current.returncode==0 and rpm.labelCompare(tuple(current.stdout.split('\t')),('0',package['version'],package['release']))>0:
                raise ValueError('Newer '+package['name']+' installed; use --allow-downgrade only for an intentional rollback')
    saved=backup();print('Settings backup: '+str(saved),flush=True)
    kernel_trees=Path('/usr/src/kernels')
    before_trees=set(kernel_trees.iterdir()) if kernel_trees.exists() else set()
    if not build.is_file():print('The running kernel has no development tree. DNF may install a newer complete kernel for DKMS; audio will require booting that kernel. No reboot is performed.',flush=True)
    command=['sudo','/usr/bin/dnf','install','-y']
    command.append('--allow-downgrade' if args.allow_downgrade else '--no-allow-downgrade')
    command += [str(ROOT/'packages'/p['file']) for p in manifest['packages'].values()]
    if not build.is_file():command += ['kernel','kernel-modules','kernel-modules-extra']
    previous_boot=None
    boot_tool=shutil.which('grubby')
    if boot_tool:
        previous_boot=subprocess.check_output(['sudo',boot_tool,'--default-kernel'],text=True).strip()
        if not previous_boot.startswith('/boot/vmlinuz-') or not Path(previous_boot).is_file():raise ValueError('Cannot preserve the current default kernel')
    try:
        subprocess.run(command,check=True)
    finally:
        if previous_boot:subprocess.run(['sudo',boot_tool,'--set-default',previous_boot],check=True)
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    print('Three RPM packages installed. Audio services have not been started.',flush=True)
    if build.is_file():
        subprocess.run(['sudo','/usr/libexec/ufxplus-linux/fedora-admin'],check=True)
        print('Start audio: systemctl --user enable --now rme-native-devices.service')
        if previous_boot and previous_boot!='/boot/vmlinuz-'+platform.release():
            print('The default boot entry remains '+previous_boot+'. RME was prepared for the running kernel '+platform.release()+'; select that kernel explicitly on your next boot. No boot-default change was made.')
    else:
        after_trees=set(kernel_trees.iterdir()) if kernel_trees.exists() else set()
        new_trees=after_trees-before_trees
        pool=new_trees or {p for p in after_trees if p.name!=platform.release() and (Path('/lib/modules')/p.name/'vmlinuz').is_file()}
        candidates=[p for p in sorted(pool) if (p/'Makefile').is_file()]
        if len(candidates)==1:
            subprocess.run(['sudo','/usr/libexec/ufxplus-linux/fedora-admin','--kernel',candidates[0].name,'--no-load'],check=True)
            print('Native ALSA is prepared for '+candidates[0].name+'. The existing default boot entry is preserved. Select the prepared kernel when ready to reboot, then run sudo /usr/libexec/ufxplus-linux/fedora-admin before starting audio.')
        else:print('Audio activation still requires exact kernel-devel for '+platform.release()+'. After installing it, run sudo /usr/libexec/ufxplus-linux/fedora-admin.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as error:raise SystemExit('RME Fedora installer: '+str(error))
