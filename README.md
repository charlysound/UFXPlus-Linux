# UFX+ Linux

A single download for the experimental RME driver, shared Linux host and
TotalMixLike. This distribution keeps the two component repositories, service
names and independent release histories intact.

## Three-family candidate bundle

Suite `0.1.0-alpha.2+devices.35` pins these component prereleases:

| Component | Version | Supported package target |
| --- | --- | --- |
| UFX+ USB3 driver | `0.1.0~alpha.12+devices.35` | `amd64` Debian package |
| Shared RME Linux host | `0.1.0~alpha.20+devices.35` | `amd64` Debian package |
| TotalMixLike | `0.2.0~alpha.51+devices.35` | `amd64` Debian package |

The exact release tags, commits, assets and SHA-256 values are in
[`components.lock.json`](components.lock.json). The package target is Linux
Mint 22 or Ubuntu 24.04 amd64. Other distributions and architectures are not
supported by this bundle.

The three pinned Debian packages are included under [`vendor/`](vendor/). Their
checksums were checked against the component releases; this keeps the public
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

## Verify or test without installing

From the extracted suite directory:

```sh
./install.sh --verify-only
./install.sh --preflight-only
```

These checks do not install packages, change settings, start services or
access the UFX+. `--preflight-only` accepts only Linux Mint 22 and Ubuntu
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

No USB audio, X11/Wayland application GUI, Secure Boot, or physical three-card
qualification is claimed for this candidate. Component release notes describe their
separate qualification and limitations.

Checksums detect accidental corruption; they do not authenticate the publisher.
Review the source repositories and release notes before installation:

- [RME UFX+ Linux USB3 driver](https://github.com/charlysound/RME-UFX-Plus-Linux-driver-USB3)
- [TotalMixLike](https://github.com/charlysound/TotalMixLike)

The component package licenses are included in each suite archive under
`licenses/`.
