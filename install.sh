#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$ROOT/fedora-manifest.json" ]]; then
    exec /usr/bin/python3 "$ROOT/fedora/install.py" "$@"
fi
MANIFEST="$ROOT/components.lock.json"
ALLOW_DOWNGRADE=0
MODE=install
if [[ $# -gt 0 ]]; then
    case "$1" in
        --allow-downgrade) ALLOW_DOWNGRADE=1 ;;
        *) MODE=$1 ;;
    esac
    shift
fi
[[ $# -eq 0 ]] || { echo "UFX+ Linux installer: unexpected argument $1" >&2; exit 1; }

fail() { echo "UFX+ Linux installer: $*" >&2; exit 1; }
usage() {
    cat <<'EOF'
Usage: ./install.sh [--verify-only|--preflight-only|--backup-only|--allow-downgrade|--help]

Default mode installs the pinned driver, RME host and TotalMixLike packages in one APT
transaction, then offers optional per-user service activation.
EOF
}

manifest_rows() {
    python3 - "$MANIFEST" <<'PY'
import json, re, sys
doc=json.load(open(sys.argv[1], encoding='utf-8'))
suite=doc['suite']
if doc.get('schema_version') != 1 or not re.fullmatch(r'[0-9A-Za-z.+~-]+', suite['version']):
    raise SystemExit('Unsupported or malformed suite manifest')
for name in ('driver','host','mixer'):
    c=doc['components'][name]
    p=c['package']
    if p['architecture'] != 'amd64' or not re.fullmatch(r'[A-Za-z0-9._+-]+_amd64\.deb', p['file']):
        raise SystemExit(f'Unsafe {name} package identity')
    if not re.fullmatch(r'[0-9a-f]{64}', p['sha256']):
        raise SystemExit(f'Invalid {name} SHA-256')
    print('\t'.join((name,p['file'],p['name'],p['version'],p['architecture'],p['sha256'])))
PY
}

verify_bundle() {
    [[ -f "$MANIFEST" && -f "$ROOT/SHA256SUMS" ]] || fail "the manifest and SHA256SUMS must remain beside this installer"
    local rows component file package version architecture expected actual
    rows=$(manifest_rows) || fail "invalid components.lock.json"
    (cd "$ROOT" && sha256sum --check --strict SHA256SUMS) || fail "suite checksum verification failed"
    command -v dpkg-deb >/dev/null || fail "this archive contains Debian packages and requires dpkg-deb; use the Fedora archive on Fedora"
    while IFS=$'\t' read -r component file package version architecture expected; do
        [[ -f "$ROOT/packages/$file" ]] || fail "missing $component package $file"
        actual=$(sha256sum -- "$ROOT/packages/$file" | cut -d ' ' -f1)
        [[ "$actual" == "$expected" ]] || fail "$component package does not match the SHA-256 pinned in components.lock.json"
        [[ "$(dpkg-deb -f "$ROOT/packages/$file" Package)" == "$package" ]] || fail "$file has the wrong Debian package name"
        [[ "$(dpkg-deb -f "$ROOT/packages/$file" Version)" == "$version" ]] || fail "$file has the wrong Debian version"
        [[ "$(dpkg-deb -f "$ROOT/packages/$file" Architecture)" == "$architecture" ]] || fail "$file has the wrong architecture"
    done <<<"$rows"
}

check_platform() {
    local os_file=${UFXPLUS_OS_RELEASE:-/etc/os-release}
    [[ -r "$os_file" ]] || fail "cannot read $os_file"
    # shellcheck disable=SC1090
    . "$os_file"
    case "${ID:-}:${VERSION_ID:-}" in
        ubuntu:24.04|linuxmint:22) ;;
        *) fail "only Ubuntu 24.04 and Linux Mint 22 are supported (found ${ID:-unknown} ${VERSION_ID:-unknown})" ;;
    esac
    [[ "$(dpkg --print-architecture)" == amd64 ]] || fail "this suite supports amd64 only"
    command -v apt-get >/dev/null || fail "APT is required"
    command -v pkexec >/dev/null || command -v sudo >/dev/null || fail "pkexec or sudo is required for the package transaction"
}

backup_settings() {
    python3 - "$MANIFEST" <<'PY'
import io, json, os, sys, tarfile
from datetime import datetime, timezone
from pathlib import Path

home=Path.home()
def xdg(variable, fallback):
    value=Path(os.environ.get(variable, str(fallback))).expanduser()
    if not value.is_absolute():
        raise SystemExit(f'{variable} must be an absolute path')
    return value
config=xdg('XDG_CONFIG_HOME', home/'.config')
state=xdg('XDG_STATE_HOME', home/'.local/state')
data=xdg('XDG_DATA_HOME', home/'.local/share')
backup_root=Path(os.environ.get('UFXPLUS_BACKUP_DIR', str(state/'ufxplus-linux/backups'))).expanduser()
if not backup_root.is_absolute():
    raise SystemExit('UFXPLUS_BACKUP_DIR must be an absolute path')
backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(backup_root,0o700)
version=json.load(open(sys.argv[1],encoding='utf-8'))['suite']['version']
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive=backup_root/f'ufxplus-linux-settings-{version}-{stamp}.tar.gz'
roots=[('XDG_CONFIG_HOME',config,'ufxplus-driver'),('XDG_CONFIG_HOME',config,'oscmix'),
       ('XDG_STATE_HOME',state,'oscmix'),('XDG_DATA_HOME',data,'oscmix')]
with tarfile.open(archive,'w:gz') as tar:
    added=[]
    for variable,base,name in roots:
        path=base/name
        if path.exists() or path.is_symlink():
            arc=f'{variable}/{name}'
            tar.add(path,arcname=arc,recursive=True)
            added.append(f'{arc}  ->  {path}')
    info='UFX+ Linux settings backup. Restore each top-level directory to its recorded XDG root.\n\n'
    info+='\n'.join(added) if added else 'No component settings directories existed when the backup was made.'
    body=info.encode()
    member=tarfile.TarInfo('RESTORE.txt'); member.size=len(body); member.mode=0o600
    tar.addfile(member,io.BytesIO(body))
os.chmod(archive,0o600)
print(archive)
PY
}

if [[ "$MODE" == --help ]]; then usage; exit 0; fi
if [[ "$MODE" == --verify-only ]]; then verify_bundle; echo "Suite files, checksums and Debian package identities are valid."; exit 0; fi
if [[ "$MODE" == --preflight-only ]]; then check_platform; echo "Supported OS and architecture."; exit 0; fi
if [[ "$MODE" == --backup-only ]]; then backup_settings; exit 0; fi
[[ "$MODE" == install ]] || fail "unknown option $MODE"

verify_bundle
check_platform
[[ "$(id -u)" != 0 ]] || fail "run as the desktop user, not as root"

for process in oscmix-gtk4 oscmix ufxplus-driver-panel ufxplus-native ufxplus-live-capture ufxplus-midi; do
    if pgrep -u "$(id -u)" -x "$process" >/dev/null 2>&1; then
        fail "$process is running; quit OSCmix and stop the audio/MIDI services before upgrading"
    fi
done
for unit in ufxplus-driver.service ufxplus-midi.service rme-native-devices.service oscmix-with-driver.service; do
    if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
        fail "$unit is active; stop the user service before upgrading"
    fi
done

mapfile -t ROWS < <(manifest_rows)
DRIVER_FILE=$(printf '%s\n' "${ROWS[0]}" | cut -f2)
HOST_FILE=$(printf '%s\n' "${ROWS[1]}" | cut -f2)
MIXER_FILE=$(printf '%s\n' "${ROWS[2]}" | cut -f2)
APT_DOWNGRADE_ARGS=()
if [[ "$ALLOW_DOWNGRADE" == 1 ]]; then APT_DOWNGRADE_ARGS+=(--allow-downgrades); fi
for pair in "ufxplus-driver:$DRIVER_FILE" "rme-native-host:$HOST_FILE" "oscmix-ufxplus:$MIXER_FILE"; do
    name=${pair%%:*}; file=${pair#*:}
    installed=$(dpkg-query -W -f='${Version}' "$name" 2>/dev/null || true)
    if [[ -n "$installed" ]]; then
        expected=$(dpkg-deb -f "$ROOT/packages/$file" Version)
        if dpkg --compare-versions "$installed" gt "$expected"; then
            if [[ "$ALLOW_DOWNGRADE" != 1 ]]; then
                fail "$name $installed is newer than this suite's $expected; rerun this verified archive with --allow-downgrade only to intentionally roll back"
            fi
        fi
    fi
done

STATE_HOME=${XDG_STATE_HOME:-"$HOME/.local/state"}
LOG_DIR="$STATE_HOME/ufxplus-linux/logs"
mkdir -p -- "$LOG_DIR"; chmod 700 "$LOG_DIR"
LOG="$LOG_DIR/install-$(date -u +%Y%m%dT%H%M%SZ).log"
BACKUP=$(backup_settings) || fail "could not back up user settings"
{
    echo "Suite $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["suite"]["version"])' "$MANIFEST")"
    echo "Settings backup: $BACKUP"
    echo "Installing packages in one APT transaction. The driver package may build its optional DKMS module for the running kernel."
} | tee -a "$LOG"

if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] && command -v pkexec >/dev/null; then
    if ! pkexec /usr/bin/apt-get install -y "${APT_DOWNGRADE_ARGS[@]}" "$ROOT/packages/$DRIVER_FILE" "$ROOT/packages/$HOST_FILE" "$ROOT/packages/$MIXER_FILE" 2>&1 | tee -a "$LOG"; then
        fail "APT failed; no service was started. Review $LOG and retain backup $BACKUP"
    fi
elif command -v sudo >/dev/null; then
    if ! sudo /usr/bin/apt-get install -y "${APT_DOWNGRADE_ARGS[@]}" "$ROOT/packages/$DRIVER_FILE" "$ROOT/packages/$HOST_FILE" "$ROOT/packages/$MIXER_FILE" 2>&1 | tee -a "$LOG"; then
        fail "APT failed; no service was started. Review $LOG and retain backup $BACKUP"
    fi
else
    fail "no usable graphical pkexec session or sudo is available for the package transaction"
fi

systemctl --user daemon-reload 2>&1 | tee -a "$LOG" || echo "Could not reload the user systemd manager; log: $LOG"
echo "Three packages installed. No service has been started automatically by this installer."
if [[ -t 0 ]]; then
    read -r -p "Enable and start the shared RME device manager for this user now? [y/N] " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        systemctl --user enable --now rme-native-devices.service 2>&1 | tee -a "$LOG"
        if [[ "${XDG_CURRENT_DESKTOP:-}" == *Cinnamon* ]] && command -v ufxplus-driver-enable-applet >/dev/null; then
            ufxplus-driver-enable-applet 2>&1 | tee -a "$LOG"
        fi
        read -r -p "Open the RME driver control panel? [y/N] " answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then rme-driver-panel; fi
    else
        echo "To start later: systemctl --user enable --now rme-native-devices.service"
    fi
fi
echo "Installation log: $LOG"
echo "Settings backup: $BACKUP"
