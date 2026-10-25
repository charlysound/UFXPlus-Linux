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

if __name__=='__main__':unittest.main()
