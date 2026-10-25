#!/usr/bin/env python3
"""Package the pinned release payloads for Fedora, without recompiling the core."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SHARED = {
    'usr/bin/ufxplus-driver-nodes', 'usr/bin/ufxplus-driver-panel',
    'usr/share/cinnamon/applets/ufxplus-driver@charlysound/applet.js',
    'usr/share/cinnamon/applets/ufxplus-driver@charlysound/metadata.json',
    'usr/share/ufxplus-driver/owner_policy.py', 'usr/share/ufxplus-driver/runtime_state.py',
    'usr/share/ufxplus-driver/session_supervisor.py',
}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def deb_payload(package, destination):
    raw = Path(package).read_bytes()
    if raw[:8] != b'!<arch>\n':
        raise ValueError('Invalid Debian archive')
    position = 8
    while position < len(raw):
        header = raw[position:position+60]
        if header[58:60] != b'`\n':
            raise ValueError('Invalid archive member')
        name = header[:16].decode().strip().rstrip('/')
        size = int(header[48:58])
        body = raw[position+60:position+60+size]
        if len(body) != size:
            raise ValueError('Truncated archive')
        if name.startswith('data.tar'):
            with tarfile.open(fileobj=io.BytesIO(body)) as archive:
                for member in archive.getmembers():
                    relative = Path(member.name.removeprefix('./'))
                    if relative == Path('.'):
                        continue
                    if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('usr','etc') or not (member.isdir() or member.isfile()):
                        raise ValueError('Unsafe payload member: ' + member.name)
                archive.extractall(destination, filter='data')
            return
        position += 60 + size + size % 2
    raise ValueError('Missing data payload')

def build(output, fedora):
    if fedora != '44':
        raise ValueError('This adapter is qualified for Fedora44 only')
    if subprocess.check_output(['rpm','--eval','%{_arch}'],text=True).strip() != 'x86_64':
        raise ValueError('An x86_64 RPM build host is required')
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):
        raise ValueError('Commit the distribution adapter before building')
    manifest = json.loads((ROOT/'components.lock.json').read_text())
    output = Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rme-fedora-build-') as temporary:
        work = Path(temporary)
        payloads = {}
        for key,item in manifest['components'].items():
            package = ROOT/'vendor'/item['package']['file']
            if digest(package) != item['package']['sha256']:
                raise ValueError('Pinned package digest mismatch: '+key)
            stage = work/key;stage.mkdir();deb_payload(package,stage);payloads[key]=stage
        overlap = {str(p.relative_to(payloads['driver'])) for p in payloads['driver'].rglob('*') if p.is_file() and (payloads['host']/p.relative_to(payloads['driver'])).is_file()}
        if overlap != SHARED:
            raise ValueError('Unexpected shared payload ownership: '+repr(overlap))
        for name in overlap:
            (payloads['driver']/name).unlink()
        patch_root=ROOT/'packaging/fedora/patches'
        module_patch=json.loads((patch_root/'source.json').read_text())
        kernel_source=payloads['host']/'usr/src/rme-pcm-0.1.0/rme_pcm.c'
        patch_file=patch_root/'rme-pcm-modern-kernel.patch'
        if digest(kernel_source)!=module_patch['before_sha256'] or digest(patch_file)!=module_patch['patch_sha256']:
            raise ValueError('Linux module patch preimage differs from pinned release')
        subprocess.run(['git','apply','--whitespace=error','-p2',str(patch_file)],cwd=kernel_source.parent,check=True)
        if digest(kernel_source)!=module_patch['after_sha256']:
            raise ValueError('Linux module patch result mismatch')
        native_rule=payloads['mixer']/'usr/lib/udev/rules.d/70-rme-native.rules'
        native_rule.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(payloads['mixer']/'usr/lib/oscmix-ufxplus/rme-runtime/70-rme-audio-preview.rules',native_rule)
        helper = payloads['host']/'usr/libexec/ufxplus-linux/fedora-admin'
        helper.parent.mkdir(parents=True);shutil.copyfile(ROOT/'packaging/fedora/admin.py',helper);helper.chmod(0o755)
        kernel = payloads['host']/'usr/src/rme-pcm-0.1.0'
        hashes = {p.name:digest(p) for p in sorted(kernel.iterdir()) if p.is_file()}
        config = payloads['host']/'usr/share/ufxplus-linux/fedora-module.json'
        config.parent.mkdir(parents=True);config.write_text(json.dumps(hashes,indent=2)+'\n')
        # RPM owns each shared replacement once; no Debian diversions are used.
        top = work/'rpmbuild'
        for name in ('BUILD','BUILDROOT','RPMS','SOURCES','SPECS','SRPMS'):(top/name).mkdir(parents=True)
        bundle = work/'ufxplus-linux-suite';(bundle/'packages').mkdir(parents=True);(bundle/'fedora').mkdir()
        packages = {}
        for key,stage in payloads.items():
            item = manifest['components'][key]['package'];name=item['name'];version=item['version'];release='2.fc'+fedora
            if not re.fullmatch(r'[A-Za-z0-9.+~_-]+',version):raise ValueError('Invalid version')
            dependencies = ['python3','python3-rpm','python3-gobject','gtk3','systemd','systemd-udev','pipewire-utils','alsa-lib','libusb1']
            if key=='host':dependencies += ['dkms','gcc','make']
            if key=='mixer':dependencies += ['gtk4','rme-native-host = '+manifest['components']['host']['package']['version']+'-'+release]
            files = [str(p.relative_to(stage)) for p in sorted(stage.rglob('*')) if p.is_file()]
            paths = '\n'.join('/'+p for p in files)
            license_expression='MIT AND GPL-2.0-only' if key=='host' else ('ISC' if key=='mixer' else 'MIT')
            spec = f'''%global debug_package %{{nil}}
%global __os_install_post %{{nil}}
Name: {name}
Version: {version}
Release: {release}
Summary: Pinned RME Linux {key} release payload
License: {license_expression}
URL: https://github.com/charlysound/UFXPlus-Linux
BuildArch: x86_64
Requires: {', '.join(dependencies)}

%description
Fedora distribution adapter for the unchanged devices35 component payload.
Audio services and kernel module activation remain explicit user operations.

%prep
%build
%install
mkdir -p %{{buildroot}}
cp -a {stage}/. %{{buildroot}}/

%post
if command -v udevadm >/dev/null; then udevadm control --reload-rules || :; fi

%files
{paths}
'''
            specfile=top/'SPECS'/(name+'.spec');specfile.write_text(spec)
            subprocess.run(['rpmbuild','-bb','--define','_topdir '+str(top),'--define','_build_id_links none',str(specfile)],check=True)
            candidates=list((top/'RPMS/x86_64').glob(name+'-'+version+'-'+release+'.x86_64.rpm'))
            if len(candidates)!=1:raise ValueError('RPM output missing: '+name)
            rpm=candidates[0];shutil.copy2(rpm,bundle/'packages'/rpm.name)
            packages[key]=dict(name=name,version=version,release=release,architecture='x86_64',file=rpm.name,sha256=digest(rpm),upstream_deb_sha256=item['sha256'],upstream_commit=manifest['components'][key]['commit'])
        data=dict(schema=1,suite_version=manifest['suite']['version'],adapter_commit=head,target=dict(id='fedora',version_id=fedora,architecture='x86_64'),packages=packages,shared_files_owned_by_host=sorted(overlap),linux_module_source=module_patch)
        (bundle/'fedora-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
        shutil.copy2(ROOT/'components.lock.json',bundle/'components.lock.json')
        shutil.copy2(ROOT/'install.sh',bundle/'install.sh')
        shutil.copy2(ROOT/'packaging/fedora/install.py',bundle/'fedora/install.py')
        shutil.copy2(ROOT/'README.md',bundle/'README.md')
        allfiles=[p for p in sorted(bundle.rglob('*')) if p.is_file()]
        (bundle/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(bundle))+'\n' for p in allfiles))
        artifact=output/f'ufxplus-linux-suite_{manifest["suite"]["version"]}_fedora{fedora}_x86_64.tar.gz'
        with tarfile.open(artifact,'w:gz') as archive:archive.add(bundle,arcname=bundle.name)
        (output/'SHA256SUMS').write_text(digest(artifact)+'  '+artifact.name+'\n')
        (output/'fedora-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
        print(artifact,flush=True)
        return artifact

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--fedora',default='44')
    args=parser.parse_args();build(args.output,args.fedora)
