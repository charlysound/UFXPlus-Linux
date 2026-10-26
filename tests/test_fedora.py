"""Archive integrity and Fedora adapter boundaries, without system changes."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
builder=module('fedora_builder','tools/build-fedora-bundle.py')
installer=module('fedora_installer','packaging/fedora/install.py')

class FedoraTests(unittest.TestCase):
    def test_actual_manifest_rejects_corrupted_rpm_before_query_or_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'packages').mkdir()
            packages={}
            for name in ('driver','host','mixer'):
                file=root/'packages'/(name+'.rpm');file.write_bytes(name.encode())
                packages[name]=dict(name=name,version='1',release='1.fc44',architecture='x86_64',file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            manifest=dict(schema=1,target=dict(id='fedora',version_id='44',architecture='x86_64'),packages=packages)
            (root/'fedora-manifest.json').write_text(json.dumps(manifest))
            (root/'SHA256SUMS').write_text(hashlib.sha256((root/'fedora-manifest.json').read_bytes()).hexdigest()+'  fedora-manifest.json\n')
            (root/'packages/driver.rpm').write_bytes(b'corrupt')
            with patch.object(installer.subprocess,'check_output') as query:
                with self.assertRaisesRegex(ValueError,'RPM differs'):installer.verify(root)
                query.assert_not_called()

    def test_rpm_header_must_match_every_pinned_component(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'packages').mkdir()
            file=root/'packages/driver.rpm';file.write_bytes(b'fixture')
            package=dict(name='driver',version='1',release='1.fc44',architecture='x86_64',file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            manifest=dict(schema=1,target=dict(id='fedora',version_id='44',architecture='x86_64'),packages={k:package for k in ('driver','host','mixer')})
            (root/'fedora-manifest.json').write_text(json.dumps(manifest));(root/'SHA256SUMS').write_text('')
            with patch.object(installer.subprocess,'check_output',return_value='other\t1\t1.fc44\tx86_64'):
                with self.assertRaisesRegex(ValueError,'RPM identity mismatch'):installer.verify(root)

    def test_release_payload_extraction_rejects_symlinks_and_traversal(self):
        for bad in ('../outside','usr/bin/link'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);body=io.BytesIO()
                with tarfile.open(fileobj=body,mode='w:xz') as archive:
                    item=tarfile.TarInfo(bad)
                    if bad.endswith('link'):item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd'
                    archive.addfile(item)
                data=body.getvalue();header=('data.tar.xz/').ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'100644'.ljust(8)+str(len(data)).ljust(10)+'`\n'
                package=root/'fixture.deb';package.write_bytes(b'!<arch>\n'+header.encode()+data)
                with self.assertRaisesRegex(ValueError,'Unsafe payload'):builder.deb_payload(package,root/'target')


# Lifecycle regressions: no root, USB, or installed-package changes.
import os
import re
import shutil
import subprocess
from types import SimpleNamespace

admin=module('fedora_admin','packaging/fedora/admin.py')

class KernelLifecycleTests(unittest.TestCase):
    def test_dkms_override_is_local_and_rejects_untested_framework(self):
        with patch.object(admin.subprocess,'check_output',return_value='dkms-3.4.4\n'), patch.dict(os.environ,{'DKMS_DIRECTIVE_OTHER':'post_transaction=bad'}):
            env=admin.dkms_env()
            self.assertEqual(env['DKMS_DIRECTIVE_RME'],'post_transaction=/usr/bin/true')
            self.assertNotIn('DKMS_DIRECTIVE_OTHER',env)
            self.assertIn('DKMS_DIRECTIVE_OTHER',os.environ)
        with patch.object(admin.subprocess,'check_output',return_value='dkms-4.0\n'):
            with self.assertRaisesRegex(ValueError,'Unsupported DKMS'):admin.dkms_env()

    def test_actual_dkms_safe_source_overrides_framework_after_config_read(self):
        path=shutil.which('dkms')
        if not path:self.skipTest('DKMS is not installed on this test host')
        source=Path(path).read_text()
        found=re.search(r'(?ms)^safe_source\(\)\s*\{.*?^\}',source)
        if not found or 'DKMS_DIRECTIVE' not in found.group():
            self.skipTest('This host does not have the supported DKMS safe_source implementation')
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'framework.conf'
            config.write_text('post_transaction="dracut --regenerate-all --force"\n')
            script='mktemp_or_die() { mktemp; }\nshow_deprecation_warnings=0\n'+found.group()+'\nsafe_source "$1" post_transaction\nprintf "%s" "$post_transaction"\n'
            env=dict(os.environ,DKMS_DIRECTIVE_RME='post_transaction=/usr/bin/true')
            result=subprocess.check_output(['/bin/bash','-c',script,'probe',str(config)],env=env,text=True)
            self.assertEqual(result,'/usr/bin/true')
            self.assertIn('--regenerate-all',config.read_text())

    def test_non_rme_image_is_never_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            boot=Path(directory);image=boot/'initramfs-test-kernel.img';image.write_bytes(b'original')
            with patch.object(admin,'BOOT',boot),patch.object(admin,'image_modules',return_value={'usr/lib/modules/test-kernel/apple-bce.ko.xz'}),patch.object(admin.subprocess,'run') as run:
                admin.clean_image('test-kernel')
                run.assert_not_called()
                self.assertEqual(image.read_bytes(),b'original')

    def test_masked_dracut_error_preserves_original_image(self):
        with tempfile.TemporaryDirectory() as directory:
            boot=Path(directory);image=boot/'initramfs-test-kernel.img';image.write_bytes(b'original')
            result=SimpleNamespace(returncode=0,stdout='',stderr="dracut[E]: FAILED: missing driver")
            with patch.object(admin,'BOOT',boot),patch.object(admin,'image_modules',return_value={'usr/lib/modules/test-kernel/snd-rme-pcm.ko.xz'}),patch.object(admin.subprocess,'run',return_value=result):
                with self.assertRaisesRegex(ValueError,'original preserved'):admin.clean_image('test-kernel')
            self.assertEqual(image.read_bytes(),b'original')

    def test_missing_unrelated_module_preserves_original_image(self):
        with tempfile.TemporaryDirectory() as directory:
            boot=Path(directory);image=boot/'initramfs-test-kernel.img';image.write_bytes(b'original')
            before={'usr/lib/modules/test-kernel/snd-rme-pcm.ko.xz','usr/lib/modules/test-kernel/apple-bce.ko.xz'}
            def run(command,**kwargs):
                if command[0]=='dracut':Path(command[-1]).write_bytes(b'incomplete')
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(admin,'BOOT',boot),patch.object(admin,'image_modules',side_effect=[before,set()]),patch.object(admin.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(ValueError,'validation failed'):admin.clean_image('test-kernel')
            self.assertEqual(image.read_bytes(),b'original')

    def test_valid_migration_replaces_only_target_image(self):
        with tempfile.TemporaryDirectory() as directory:
            boot=Path(directory);image=boot/'initramfs-test-kernel.img';image.write_bytes(b'original')
            other=boot/'initramfs-other-kernel.img';other.write_bytes(b'untouched')
            kept={'usr/lib/modules/test-kernel/apple-bce.ko.xz'}
            def run(command,**kwargs):
                if command[0]=='dracut':
                    self.assertNotIn('--regenerate-all',command)
                    Path(command[-1]).write_bytes(b'checked')
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(admin,'BOOT',boot),patch.object(admin,'image_modules',side_effect=[kept|{'usr/lib/modules/test-kernel/snd-rme-pcm.ko.xz'},kept]),patch.object(admin.subprocess,'run',side_effect=run):
                admin.clean_image('test-kernel')
            self.assertEqual(image.read_bytes(),b'checked')
            self.assertEqual(other.read_bytes(),b'untouched')

    def test_active_owner_blocks_kernel_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            proc=Path(directory);(proc/'123').mkdir()
            (proc/'123/cmdline').write_bytes(b'/usr/bin/python3\0/usr/lib/oscmix-ufxplus/rme-runtime/auto.py\0')
            with patch.object(admin,'PROC',proc):
                with self.assertRaisesRegex(ValueError,'Stop the RME'):admin.require_idle()

    def test_busy_module_blocks_even_without_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'refcnt').write_text('2\n')
            with patch.object(admin,'PROC',root),patch.object(admin,'SYS_MODULE',root):
                with self.assertRaisesRegex(ValueError,'in use'):admin.require_idle()

    def test_removal_cleans_all_registered_kernels_with_hook_isolation(self):
        status='rme-pcm/0.1.0, first-kernel, x86_64: installed\nrme-pcm/0.1.0, second-kernel, x86_64: installed\n'
        env={'DKMS_DIRECTIVE_RME':'post_transaction=/usr/bin/true'}
        with patch.object(admin.os,'geteuid',return_value=0),patch.object(admin,'dkms_env',return_value=env),patch.object(admin,'require_idle') as idle,patch.object(admin,'clean_image') as clean,patch.object(admin.subprocess,'check_output',return_value=status),patch.object(admin,'SYS_MODULE',Path('/nonexistent-rme-test-module')),patch.object(admin,'dkms') as dkms:
            admin.remove()
            idle.assert_called_once()
            self.assertEqual(clean.call_args_list,[unittest.mock.call('first-kernel'),unittest.mock.call('second-kernel')])
            dkms.assert_called_once_with(['remove','-m','rme-pcm','-v','0.1.0','--all'],env)

    def test_rpm_removal_hook_skips_upgrade_and_propagates_busy_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            helper=Path(directory)/'helper';called=Path(directory)/'called'
            helper.write_text('#!/bin/sh\nprintf "%s" "$*" > "'+str(called)+'"\nexit 23\n');helper.chmod(0o755)
            hook=builder.HOST_PREUN.removeprefix('%preun\n').replace('/usr/libexec/ufxplus-linux/fedora-admin',str(helper))
            self.assertEqual(subprocess.run(['/bin/sh','-c',hook,'preun','1']).returncode,0)
            self.assertFalse(called.exists())
            self.assertEqual(subprocess.run(['/bin/sh','-c',hook,'preun','0']).returncode,23)
            self.assertEqual(called.read_text(),'--remove')

if __name__=='__main__':unittest.main()
