# UFX+ Linux

## Joint Mint 22 / Fedora 44 candidate

This PR prepares suite `0.1.0-alpha.5+devices.35`, with two archives under one
release: `*_amd64.tar.gz` for Mint 22.x / Ubuntu 24.04 and
`*_fedora44_x86_64.tar.gz` for Fedora 44. It pins the driver alpha.13 release
(UFX+ package alpha.12 and shared host alpha.21) with TotalMixLike alpha.67.
OSCmix adds ARC preamp assignments, paired preamp gains, Dynamics, F4–F8 actions
and guarded USB protocol handover. Software tests do not qualify physical ARC
buttons, LEDs or wheel behavior.

Both CI targets must pass before a version tag can create a release draft with
both archives and a combined `SHA256SUMS`. Publication remains an explicit final
step. See [joint release procedure and qualification](docs/joint-release.md).

## What's New in alpha.5

- TotalMixLike advances from alpha.51 to alpha.67, including ARC preamp
  assignments, paired gain commands, Dynamics Gain 1–4 and F4–F8 actions.
- Mint and Fedora packaging checks follow the pinned component versions.
- Fedora preserves the previously shipped USB access rule; its SHA-256 is
  checked directly against the recorded alpha.4 policy fingerprint.
- Both archives must pass installation, upgrade and removal checks before
  the release can be staged.
- The mixer includes the manifest-verified audio/MIDI runtime and matching
  control producer. Both archive builders reject missing or mismatched inputs.
- Mint checks a fresh installation and the real alpha.51 → alpha.67 package
  upgrade from the published alpha.4 suite, preserving settings.

- Native FX panels stay aligned when nested preset menus open; offline USB
  service regression checks preserve cadence and pipe-priority coverage.

- Source GUI checks use a private session bus and bounded event waits, with
  a regression that detects a continuously busy event-loop stall.

## Fedora 44 experimental distribution

The Fedora archive uses the three component releases pinned below and native RPM
ownership and DNF dependencies. It packages the same pinned driver payloads as
the Mint archive and includes the updated TotalMixLike alpha.67 package. Its small
common ALSA module source includes a pinned Linux header compatibility fix,
recorded in `fedora-manifest.json`; this is shared by every card model. The
Fedora adapter retains the exact USB uaccess rule from the previous alpha.51
package. It does not derive device
permissions from alpha.67's passive identity catalogue. The Mint DEB and Fedora
RPM carry the same patched module source and shared lifecycle guard.

Extract `ufxplus-linux-suite_0.1.0-alpha.5+devices.35_fedora44_x86_64.tar.gz`, then
run `./install.sh` as your desktop user. `--verify-only` checks the RPM identities
and checksums; `--preflight-only` reports the actual platform and kernel build
tree. The installer backs up XDG settings and refuses upgrades while a component
service is running. Packages install in one DNF transaction; services remain
stopped until explicitly enabled.

Audio needs the external `snd-rme-pcm` ALSA module. DKMS builds this small module,
not the RME audio core or GUI. Install the exact `kernel-devel` matching `uname -r`
from your kernel provider, then run `sudo /usr/libexec/ufxplus-linux/fedora-admin`.
For an Apple T2 kernel the matching T2 development package is required; generic
Fedora headers are insufficient. Kernel loading retains the host's Secure Boot
policy. If the current kernel headers are unavailable, DNF installs a complete
newer kernel and its development package; the installer prepares the module for
that kernel. Where `grubby` is available, the previous default boot entry is
restored after the package transaction. No reboot is performed.

After successful module preparation:

```sh
systemctl --user enable --now rme-native-devices.service
rme-driver-panel
oscmix-ufxplus
```

Runtime dependencies are resolved by DNF. Rust, Cargo and GTK development headers
are not needed to run these release binaries. RPM bundle generation is a separate
maintainer operation: `python3 tools/build-fedora-bundle.py --output dist-fedora`.
[Fedora qualification and known limits](docs/fedora-qualification.md) describe
the exact tested combination, with the previous hardware evidence kept distinct from this joint candidate.

RPM revision `5.fc44` isolates its DKMS operations from Fedora's global
`post_transaction` hook. It supports DKMS 3.4 (at least 3.4.4) and never changes
the host framework configuration. The desktop frontend does not need to be in
an initramfs. Fresh installations leave boot images untouched. An existing
target image containing an earlier RME module is rebuilt without it in a
temporary file, checked for dracut errors and missing unrelated modules, then
replaced atomically. Other kernel images and the default boot choice are kept.
DKMS operations launched independently by the operating system retain its own
configured hooks; this package does not repair a kernel provider's configuration.

To uninstall, close OSCmix, stop the RME user services, then run
`./install.sh --uninstall` from the verified suite. Settings are backed up and
preserved. Final host RPM removal refuses active owners or a busy module,
cleans DKMS registrations and installed modules for all registered kernels,
and unloads the idle frontend. RPM upgrades retain the existing registration
until the explicit preparation step rebuilds it; they do not run removal.

A single download for the experimental RME driver, shared Linux host and
TotalMixLike. This distribution keeps the two component repositories, service
names and independent release histories intact.

## Three-family candidate bundle

Suite `0.1.0-alpha.5+devices.35` pins two component prereleases and the updated host package:

| Component | Version | Supported package target |
| --- | --- | --- |
| UFX+ USB3 driver | `0.1.0~alpha.12+devices.35` | `amd64` Debian package |
| Shared RME Linux host | `0.1.0~alpha.21+devices.35` | `amd64` Debian package |
| TotalMixLike | `0.2.0~alpha.67+commands.2` | `amd64` Debian package |

The exact release tags, commits, assets and SHA-256 values are in
[`components.lock.json`](components.lock.json). The original Debian archive targets
Linux Mint 22 or Ubuntu 24.04 amd64. Fedora44 uses the separate RPM archive described
above; its qualification is recorded independently. Other targets remain untested.

The three pinned Debian packages are included under [`vendor/`](vendor/). Their
driver/mixer checksums match their component releases; the host candidate records its exact source commit, build input and SHA-256. This keeps the public
bundle build reproducible without granting this repository access to the
private component source repositories.

## Install

Download and extract the suite archive from the [UFX+ Linux releases](https://github.com/charlysound/UFXPlus-Linux/releases),
then run:

```sh
./install.sh
```

The installer verifies every bundled file and all three Debian package identities,
backs up the current user's driver and OSCmix settings, and installs the three
packages in one APT transaction. It refuses to upgrade while the driver,
RME host, MIDI bridge or mixer is running. Quit the mixer and stop the user services
before retrying. The backup location is printed and recorded in the install
log under `~/.local/state/ufxplus-linux/`.

From a graphical desktop session, package authorization uses `pkexec`; in a
headless session it uses `sudo` in the terminal.

Installation does not start audio services as root. At the end, the installer
offers to enable and start the shared RME device manager for the current user
and open the driver panel. Declining leaves service state unchanged. Open
OSCmix from its desktop launcher; the old UFX+-only companion service remains
available for installations that deliberately use the legacy UFX+ owner.

The shared host package builds its `rme-pcm` kernel module through DKMS for the
running kernel. Matching kernel headers and DKMS must be available before
installation. Its post-install hook reloads udev rules but does not reset or
retrigger USB devices. Installing the package does not qualify audio on hardware.

The installer preserves these user data directories when present:

- `$XDG_CONFIG_HOME/ufxplus-driver` and `$XDG_CONFIG_HOME/oscmix`
- `$XDG_STATE_HOME/oscmix`
- `$XDG_DATA_HOME/oscmix`

The defaults follow the XDG specification (`~/.config`, `~/.local/state` and
`~/.local/share`). The backup is a private, user-owned tar archive and is not
uploaded.

To remove the Mint suite, stop its user services and run `./install.sh --uninstall`.
The installer backs up settings and removes the three packages in one APT
transaction. The host's `prerm` refuses a busy module or active runtime, removes
DKMS registrations before deleting sources, and restores legacy diversions.
If an older Debian initramfs embeds RME, removal stops with the original image
and sources retained; migrate that image before retrying. Package-owned DKMS
calls keep host framework configuration unchanged (DKMS 3.0–3.4).

## Verify or test without installing

From the extracted suite directory:

```sh
./install.sh --verify-only
./install.sh --preflight-only
```

These checks do not install packages, change settings, start services or
access the UFX+. `--preflight-only` accepts Linux Mint 22.x and Ubuntu
24.04 on amd64.

## Rollback

Keep the previous suite archive until the new installation has been checked.
To return to that exact pair, stop the user services and run the previous
archive's `./install.sh --allow-downgrade`. The option applies only to that
verified archive: the installer still checks every checksum and package
identity, saves settings, and installs all three packages in one APT transaction.
Without the explicit option, the installer refuses to replace a newer installed
version. The settings backup remains available if an application ever needs
its previous configuration restored. To remove a first-time installation,
use APT with the package names shown by `dpkg-query -W ufxplus-driver
rme-native-host oscmix-ufxplus`; user settings are not removed by package removal.

## Scope and qualification

This is community packaging, not an official RME driver. This candidate bundle
combines three packages from two component prereleases; the suite's build checks verify
package identity, archive contents and checksums. CI does not install the
packages into a VM or test USB audio.

The preceding two-package suite `0.1.0-alpha.1` passed manual Mint 22 and
Ubuntu 24.04 VM installation tests. Those results do not qualify this new
three-package transaction. The candidate needs fresh VM and physical checks
for Babyface, UFX+ and Digiface Dante before normal installation is advised.

The Fedora checks and their limits are documented separately above. Secure Boot
and physical three-card qualification are not claimed for this candidate. Component
release notes describe their separate qualification and limitations.

Checksums detect accidental corruption; they do not authenticate the publisher.
Review the source repositories and release notes before installation:

- [RME UFX+ Linux USB3 driver](https://github.com/charlysound/RME-UFX-Plus-Linux-driver-USB3)
- [TotalMixLike](https://github.com/charlysound/TotalMixLike)

The component package licenses are included in each suite archive under
`licenses/`.
