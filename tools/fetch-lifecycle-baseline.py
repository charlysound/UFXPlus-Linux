#!/usr/bin/env python3
"""Fetch immutable, checksum-pinned distribution upgrade fixtures."""
import argparse
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = ('https://github.com/charlysound/UFXPlus-Linux/releases/download/'
       'v0.1.0-alpha.3%2Bdevices.35/'
       'ufxplus-linux-suite_0.1.0-alpha.3%2Bdevices.35_fedora44_x86_64.tar.gz')
SHA256 = '71d3a2bc656f688a250fd9cba4eaff6c92418c07f843b58fc68c4907b1c8084c'
MINT_URL = ('https://github.com/charlysound/UFXPlus-Linux/releases/download/'
            'v0.1.0-alpha.4%2Bdevices.35/'
            'ufxplus-linux-suite_0.1.0-alpha.4%2Bdevices.35_amd64.tar.gz')
MINT_SHA256 = '4461e4ac5ff3fce7ef7e774c8312900003d4ccd9480ecba3a730d663eb695262'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--target', choices=('fedora', 'mint'), default='fedora')
    args = parser.parse_args()
    directory = args.directory; directory.mkdir(exist_ok=False)
    url, digest, extension = ((MINT_URL, MINT_SHA256, '.deb') if args.target == 'mint'
                              else (URL, SHA256, '.rpm'))
    data = urllib.request.urlopen(url, timeout=90).read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit('Previous release checksum differs')
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        packages = [m for m in archive.getmembers() if m.name.startswith('ufxplus-linux-suite/packages/') and m.name.endswith(extension)]
        if len(packages) != 3:
            raise SystemExit('Expected three baseline packages')
        for member in packages:
            if not member.isfile() or Path(member.name).name in ('', '.', '..'):
                raise SystemExit('Unsafe baseline member')
            (directory/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    print('Verified '+args.target+' upgrade baseline: '+digest)
