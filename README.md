# UFX+ Linux

A single download for the experimental RME Fireface UFX+ USB3 driver and
TotalMixLike. This distribution keeps the two component repositories,
packages, service names and independent release histories intact.

## First bundle

Suite `0.1.0-alpha.1` pins these published component releases:

| Component | Version | Supported package target |
| --- | --- | --- |
| UFX+ USB3 driver | `0.1.0~alpha.11+alsa.6` | `amd64` Debian package |
| TotalMixLike | `0.2.0~alpha.26+menus.2` | `amd64` Debian package |

The exact release tags, commits, assets and SHA-256 values are in
[`components.lock.json`](components.lock.json). The initial target is Linux
Mint 22 or Ubuntu 24.04 amd64. Other distributions and architectures are not
supported by this bundle.

The two pinned Debian packages are included under [`vendor/`](vendor/). Their
checksums were checked against the component releases; this keeps the public
bundle build reproducible without granting this repository access to the
private component source repositories.

## Install

Download and extract the suite archive from the [UFX+ Linux releases](https://github.com/charlysound/UFXPlus-Linux/releases),
then run:

```sh
./install.sh
```

The installer verifies every bundled file and both Debian package identities,
backs up the current user's UFX+ driver and OSCmix settings, and installs both
packages in one APT transaction. It refuses to upgrade while the driver,
MIDI bridge or mixer is running. Quit the mixer and stop the user services
before retrying. The backup location is printed and recorded in the install
log under `~/.local/state/ufxplus-linux/`.

Installation does not start audio services as root. At the end, the installer
offers to enable and start the driver for the current user, enable the optional
OSCmix companion, and open the driver panel. Declining leaves service state
unchanged. OSCmix's existing user-session autostart integration remains
available when its companion service is enabled.

The driver's Debian post-install hook can compile its optional DKMS module for
the running kernel when DKMS is already installed. That step needs matching
kernel headers and is performed by APT during package configuration. The
package reloads udev rules but does not reset or retrigger USB devices.

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
archive's `install.sh`; it installs both previous packages together. The
settings backup remains available if an application ever needs its previous
configuration restored. To remove a first-time installation, use APT with the
package names shown by `dpkg-query -W ufxplus-driver oscmix-ufxplus`; user
settings are not removed by package removal.

## Scope and qualification

This is community packaging, not an official RME driver. The initial bundle
combines two individually published releases; the suite's build checks verify
package identity, archive contents and checksums. CI does not test USB audio,
install or update the packages on a virtual machine, or establish audio
qualification for this combined release. Those results remain explicitly
unverified until evidence is added. Component release notes describe their
separate qualification and limitations.

Checksums detect accidental corruption; they do not authenticate the publisher.
Review the source repositories and release notes before installation:

- [RME UFX+ Linux USB3 driver](https://github.com/charlysound/RME-UFX-Plus-Linux-driver-USB3)
- [TotalMixLike](https://github.com/charlysound/TotalMixLike)

The component package licenses are included in each suite archive under
`licenses/`.
