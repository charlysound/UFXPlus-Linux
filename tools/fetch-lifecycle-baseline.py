#!/usr/bin/env python3
"""Fetch the immutable, checksum-pinned Fedora RPM4 upgrade fixture."""
import hashlib
import io
from pathlib import Path
import sys
import tarfile
import urllib.request

URL = ('https://github.com/charlysound/UFXPlus-Linux/releases/download/'
       'v0.1.0-alpha.3%2Bdevices.35/'
       'ufxplus-linux-suite_0.1.0-alpha.3%2Bdevices.35_fedora44_x86_64.tar.gz')
SHA256 = '71d3a2bc656f688a250fd9cba4eaff6c92418c07f843b58fc68c4907b1c8084c'


if __name__ == '__main__':
    directory = Path(sys.argv[1]); directory.mkdir(exist_ok=False)
    data = urllib.request.urlopen(URL, timeout=90).read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('Previous release checksum differs')
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        packages = [m for m in archive.getmembers() if m.name.startswith('ufxplus-linux-suite/packages/') and m.name.endswith('.rpm')]
        if len(packages) != 3:
            raise SystemExit('Expected three baseline RPMs')
        for member in packages:
            if not member.isfile() or Path(member.name).name in ('', '.', '..'):
                raise SystemExit('Unsafe baseline member')
            (directory/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    print('Verified RPM4 upgrade baseline: '+SHA256)
