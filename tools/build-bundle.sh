#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-"$ROOT/dist"}
OUT=$(mkdir -p -- "$OUT" && cd -- "$OUT" && pwd)
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ufxplus-suite-build.XXXXXX")
trap 'rm -rf -- "$WORK"' EXIT
STAGE="$WORK/ufxplus-linux-suite"
mkdir -p "$STAGE/packages" "$STAGE/licenses" "$STAGE/metadata"

python3 - "$ROOT/components.lock.json" >"$WORK/assets.tsv" <<'PY'
import json, sys
doc=json.load(open(sys.argv[1], encoding='utf-8'))
for name in ('driver','mixer'):
    item=doc['components'][name]
    package=item['package']
    print('\t'.join((name, package['file'], package['sha256'],
                     package['copyright_path'], package['name'], package['version'],
                     package['architecture'])))
PY

while IFS=$'\t' read -r component file expected copyright package version architecture; do
    [[ "$file" =~ ^[A-Za-z0-9._+-]+_amd64\.deb$ ]] || { echo "Unsafe package filename: $file" >&2; exit 1; }
    source="$ROOT/vendor/$file"
    [[ -f "$source" ]] || { echo "Missing vendored pinned package: $source" >&2; exit 1; }
    echo "Adding pinned $component package $version"
    cp -- "$source" "$STAGE/packages/$file"
    actual=$(sha256sum -- "$STAGE/packages/$file" | cut -d ' ' -f1)
    [[ "$actual" == "$expected" ]] || { echo "SHA-256 mismatch for $file" >&2; exit 1; }
    [[ "$(dpkg-deb -f "$STAGE/packages/$file" Package)" == "$package" ]]
    [[ "$(dpkg-deb -f "$STAGE/packages/$file" Version)" == "$version" ]]
    [[ "$(dpkg-deb -f "$STAGE/packages/$file" Architecture)" == "$architecture" ]]
    extract="$WORK/extract-$component"
    mkdir -p "$extract"
    dpkg-deb -x "$STAGE/packages/$file" "$extract"
    [[ -f "$extract/$copyright" ]] || { echo "Missing component copyright: $copyright" >&2; exit 1; }
    cp -- "$extract/$copyright" "$STAGE/licenses/$component-copyright"
done <"$WORK/assets.tsv"

cp -- "$ROOT/README.md" "$ROOT/components.lock.json" "$ROOT/install.sh" "$STAGE/"
suite_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["suite"]["version"])' "$ROOT/components.lock.json")
printf '%s\n' "$suite_version" >"$STAGE/metadata/suite-version"
(cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)

archive="$OUT/ufxplus-linux-suite_${suite_version}_amd64.tar.gz"
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='@0' -C "$WORK" -czf "$archive" ufxplus-linux-suite
(cd "$OUT" && sha256sum "$(basename -- "$archive")" >SHA256SUMS)
echo "Built $archive"
