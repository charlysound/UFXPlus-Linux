import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('baseline', Path(__file__).resolve().parents[1]/'tools/fetch-lifecycle-baseline.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class CachedBaseline(unittest.TestCase):
    def test_cache_uses_the_same_hash_gate_without_a_network_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)/'fixture.tar.gz'
            archive.write_bytes(b'published fixture')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.object(baseline.urllib.request,'urlopen',side_effect=AssertionError('No network')):
                self.assertEqual(baseline.verified_bytes(archive,'https://example.invalid',digest),b'published fixture')
                archive.write_bytes(b'corrupt fixture')
                with self.assertRaisesRegex(ValueError,'checksum differs'):
                    baseline.verified_bytes(archive,'https://example.invalid',digest)

    def test_published_baselines_are_pinned_and_platform_specific(self):
        for url in (baseline.URL,baseline.MINT_URL):
            self.assertIn('v0.1.0-alpha.5%2Bdevices.35/',url)
        self.assertRegex(baseline.SHA256,r'^[0-9a-f]{64}$')
        self.assertRegex(baseline.MINT_SHA256,r'^[0-9a-f]{64}$')
        self.assertNotEqual(baseline.SHA256,baseline.MINT_SHA256)
