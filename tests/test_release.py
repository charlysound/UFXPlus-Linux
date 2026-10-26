import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('joint_release', ROOT/'tools/prepare-release.py')
release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)


class JointRelease(unittest.TestCase):
    def fixture(self, root, *, commit='current', corrupt=False):
        lock = {'suite': {'version': '1.2.3'}, 'components': {}}
        for target, suffix in (('mint', 'amd64'), ('fedora', 'fedora44_x86_64')):
            directory = root/target; directory.mkdir()
            files = {'components.lock.json': json.dumps(lock).encode(), 'payload': b'pinned'}
            if target == 'mint':
                files['metadata/source-commit'] = commit.encode()
            else:
                files['fedora-manifest.json'] = json.dumps({'suite_version': '1.2.3', 'adapter_commit': commit}).encode()
            files['SHA256SUMS'] = ''.join(hashlib.sha256(body).hexdigest()+'  '+name+'\n' for name, body in files.items()).encode()
            if corrupt and target == 'fedora': files['payload'] = b'changed'
            with tarfile.open(directory/('suite_1.2.3_'+suffix+'.tar.gz'), 'w:gz') as archive:
                for name, body in files.items():
                    member = tarfile.TarInfo('ufxplus-linux-suite/'+name); member.size = len(body)
                    archive.addfile(member, io.BytesIO(body))
        return lock

    def test_two_matching_archives_stage_together(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); lock = self.fixture(root)
            release.prepare(root, 'v1.2.3', lock, 'current')
            self.assertEqual(len(list((root/'upload').glob('*.tar.gz'))), 2)
            self.assertEqual(len((root/'upload/SHA256SUMS').read_text().splitlines()), 2)

    def test_missing_target_corruption_stale_commit_and_wrong_tag_block_delivery(self):
        for problem in ('missing', 'corrupt', 'commit', 'tag'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                lock = self.fixture(root, commit='old' if problem == 'commit' else 'current', corrupt=problem == 'corrupt')
                if problem == 'missing': next((root/'fedora').glob('*.tar.gz')).unlink()
                with self.assertRaises(ValueError):
                    release.prepare(root, 'v9' if problem == 'tag' else 'v1.2.3', lock, 'current')
                self.assertFalse((root/'upload').exists())


if __name__ == '__main__': unittest.main()
