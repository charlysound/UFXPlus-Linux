#!/usr/bin/env python3
"""Fetch immutable, checksum-pinned distribution upgrade fixtures."""
import argparse
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = ('https://github.com/charlysound/UFXPlus-Linux/releases/download/'
       'v0.1.0-alpha.5%2Bdevices.35/'
       'ufxplus-linux-suite_0.1.0-alpha.5%2Bdevices.35_fedora44_x86_64.tar.gz')
SHA256 = '95cea9cddbc2e402c7ada15dda0a8cf2c19e0a454756fa8988634c1fecf67cf3'
MINT_URL = ('https://github.com/charlysound/UFXPlus-Linux/releases/download/'
            'v0.1.0-alpha.5%2Bdevices.35/'
            'ufxplus-linux-suite_0.1.0-alpha.5%2Bdevices.35_amd64.tar.gz')
MINT_SHA256 = '5a7ba7362de68e8ed227ab7b2ee26db8b5d3ea07ca29705c1c12a15078a7bf24'


def verified_bytes(archive, url, digest):
    data = archive.read_bytes() if archive else urllib.request.urlopen(url, timeout=90).read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Previous release checksum differs')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--target', choices=('fedora', 'mint'), default='fedora')
    parser.add_argument('--archive', type=Path, help='Reuse a local published archive; the same pinned checksum is required')
    args = parser.parse_args()
    directory = args.directory; directory.mkdir(exist_ok=False)
    url, digest, extension = ((MINT_URL, MINT_SHA256, '.deb') if args.target == 'mint'
                              else (URL, SHA256, '.rpm'))
    try:
        data = verified_bytes(args.archive, url, digest)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        packages = [m for m in archive.getmembers() if m.name.startswith('ufxplus-linux-suite/packages/') and m.name.endswith(extension)]
        if len(packages) != 3:
            raise SystemExit('Expected three baseline packages')
        for member in packages:
            if not member.isfile() or Path(member.name).name in ('', '.', '..'):
                raise SystemExit('Unsafe baseline member')
            (directory/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    print('Verified '+args.target+' upgrade baseline: '+digest)
