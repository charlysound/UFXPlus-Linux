#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/ufxplus-suite-test.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
BUNDLE="$TMP/bundle"
mkdir -p "$BUNDLE/packages" "$BUNDLE/licenses"
cp "$ROOT/install.sh" "$ROOT/README.md" "$ROOT/components.lock.json" "$BUNDLE/"

make_deb() {
    local name=$1 version=$2 filename=$3 work="$TMP/$1"
    mkdir -p "$work/DEBIAN"
    cat >"$work/DEBIAN/control" <<EOF
Package: $name
Version: $version
Architecture: amd64
Maintainer: UFX+ Linux test <noreply@example.invalid>
Description: installer fixture
EOF
    dpkg-deb --build "$work" "$BUNDLE/packages/$filename" >/dev/null
}

make_deb ufxplus-driver '0.1.0~alpha.11+alsa.6' 'ufxplus-driver_0.1.0-alpha.11+alsa.6_amd64.deb'
make_deb oscmix-ufxplus '0.2.0~alpha.26+menus.2' 'oscmix-ufxplus_0.2.0-alpha.26+menus.2_amd64.deb'
python3 - "$BUNDLE/components.lock.json" "$BUNDLE/packages" <<'PY'
import hashlib, json, sys
path, packages=sys.argv[1:]
doc=json.load(open(path,encoding='utf-8'))
for component in doc['components'].values():
    package=component['package']
    package['sha256']=hashlib.sha256(open(packages+'/'+package['file'],'rb').read()).hexdigest()
open(path,'w',encoding='utf-8').write(json.dumps(doc,indent=2)+'\n')
PY
(cd "$BUNDLE" && sha256sum README.md components.lock.json install.sh packages/*.deb >SHA256SUMS)

"$BUNDLE/install.sh" --verify-only

printf 'ID=ubuntu\nVERSION_ID="24.04"\n' >"$TMP/ubuntu-release"
UFXPLUS_OS_RELEASE="$TMP/ubuntu-release" "$BUNDLE/install.sh" --preflight-only
printf 'ID=linuxmint\nVERSION_ID="22"\n' >"$TMP/mint-release"
UFXPLUS_OS_RELEASE="$TMP/mint-release" "$BUNDLE/install.sh" --preflight-only
printf 'ID=fedora\nVERSION_ID="43"\n' >"$TMP/fedora-release"
if UFXPLUS_OS_RELEASE="$TMP/fedora-release" "$BUNDLE/install.sh" --preflight-only >/dev/null 2>&1; then
    echo "Unsupported OS was accepted" >&2; exit 1
fi

mkdir -p "$TMP/home/config/ufxplus-driver" "$TMP/home/config/oscmix" "$TMP/home/state/oscmix" "$TMP/home/data/oscmix" "$TMP/home/backups"
printf 'driver-node-selection\n' >"$TMP/home/config/ufxplus-driver/nodes.json"
printf 'mixer-preferences\n' >"$TMP/home/config/oscmix/appearance.ini"
printf 'snapshot-matrix\n' >"$TMP/home/state/oscmix/ufxplus-native-matrix.ini"
printf 'workspace-data\n' >"$TMP/home/data/oscmix/workspaces"
HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/home/config" XDG_STATE_HOME="$TMP/home/state" \
XDG_DATA_HOME="$TMP/home/data" UFXPLUS_BACKUP_DIR="$TMP/home/backups" \
    "$BUNDLE/install.sh" --backup-only >"$TMP/backup-path"
backup=$(cat "$TMP/backup-path")
[[ -f "$backup" && "$(stat -c %a "$backup")" == 600 ]]
tar -tzf "$backup" | grep -Fq 'XDG_CONFIG_HOME/ufxplus-driver/nodes.json'
tar -tzf "$backup" | grep -Fq 'XDG_CONFIG_HOME/oscmix/appearance.ini'
tar -tzf "$backup" | grep -Fq 'XDG_STATE_HOME/oscmix/ufxplus-native-matrix.ini'
tar -tzf "$backup" | grep -Fq 'XDG_DATA_HOME/oscmix/workspaces'

# A newer installed version is rejected by default; an explicit rollback from
# this checksum-verified archive must pass APT's downgrade authorization.
FAKE_BIN="$TMP/fake-bin"
mkdir -p "$FAKE_BIN"
cat >"$FAKE_BIN/dpkg-query" <<'EOF'
#!/usr/bin/env bash
case "${@: -1}" in
    ufxplus-driver) echo '9.9.0' ;;
    oscmix-ufxplus) echo '9.9.0' ;;
    *) exit 1 ;;
esac
EOF
cat >"$FAKE_BIN/sudo" <<EOF
#!/usr/bin/env bash
printf '%s\\n' "\$*" >>"$TMP/apt-args"
[[ " \$* " == *" --allow-downgrades "* ]]
EOF
cat >"$FAKE_BIN/systemctl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"is-active"* ]]; then exit 1; fi
exit 0
EOF
chmod +x "$FAKE_BIN/dpkg-query" "$FAKE_BIN/sudo" "$FAKE_BIN/systemctl"
if PATH="$FAKE_BIN:$PATH" HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/home/config" \
   XDG_STATE_HOME="$TMP/home/state" XDG_DATA_HOME="$TMP/home/data" \
   UFXPLUS_BACKUP_DIR="$TMP/home/backups" "$BUNDLE/install.sh" >"$TMP/downgrade-refusal" 2>&1; then
    echo "Downgrade without explicit opt-in was accepted" >&2; exit 1
fi
grep -Fq -- '--allow-downgrade' "$TMP/downgrade-refusal"
PATH="$FAKE_BIN:$PATH" HOME="$TMP/home" XDG_CONFIG_HOME="$TMP/home/config" \
XDG_STATE_HOME="$TMP/home/state" XDG_DATA_HOME="$TMP/home/data" \
UFXPLUS_BACKUP_DIR="$TMP/home/backups" \
    "$BUNDLE/install.sh" --allow-downgrade >"$TMP/downgrade-allowed" 2>&1
grep -Fq -- '--allow-downgrades' "$TMP/apt-args"

cp "$BUNDLE/packages/ufxplus-driver_0.1.0-alpha.11+alsa.6_amd64.deb" "$TMP/driver.deb"
printf '\ncorruption\n' >>"$BUNDLE/packages/ufxplus-driver_0.1.0-alpha.11+alsa.6_amd64.deb"
if "$BUNDLE/install.sh" --verify-only >/dev/null 2>&1; then
    echo "Corrupt package checksum was accepted" >&2; exit 1
fi
mv "$TMP/driver.deb" "$BUNDLE/packages/ufxplus-driver_0.1.0-alpha.11+alsa.6_amd64.deb"

echo "Installer tests passed (verification, supported OS gate, backup preservation, downgrade opt-in, corruption rejection)."
