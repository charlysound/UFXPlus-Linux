# UFX+ Linux

Experimental native RME USB audio/MIDI, shared Linux settings and
[TotalMixLike](https://github.com/charlysound/TotalMixLike) mixer in one installer.
This is an independent project, not an official RME driver or TotalMix release.

## Download and install

Use the [release assets](https://github.com/charlysound/UFXPlus-Linux/releases),
not GitHub's automatic source-code archive.

- Linux Mint 22.x amd64: `*_amd64.tar.gz` (three DEB packages).
- Fedora 44 x86_64: `*_fedora44_x86_64.tar.gz` (three RPM packages).

Both archives include an installer, exact component lock, licenses and checksums.
Extract the appropriate archive, open a terminal inside it and run:

```sh
./install.sh --verify-only
./install.sh --preflight-only
./install.sh
```

Run as your desktop user; the installer requests package-manager authorization.
Do not run the GUI as root. Rust/Cargo and GTK development headers are not
needed to use release binaries.

The installer backs up XDG settings, verifies package hashes/identities and
refuses upgrades while component services or the mixer are running. Close
the mixer and stop the RME user services before an upgrade. This is intentional:
replacing files does not reload an already-running owner or an app-local runtime.
Declining optional service startup leaves activation to you.

## What's new in alpha.7

Suite `0.1.0-alpha.7+dante.1` includes one archive for Linux Mint 22.x
and one for Fedora 44 under the same release.

| Component | Version |
| --- | --- |
| Legacy UFX+ USB3 package | `0.1.0~alpha.30+dante.1` |
| Shared RME Linux host/settings | `0.1.0~alpha.30+dante.1` |
| TotalMixLike mixer | `0.2.0~alpha.97+dante.1` |

- Digiface Dante USB Settings follows the native availability rules for the
  Ethernet mode display, Preferred Leader and Isochronous Transfer.
- Mixer control waits for the selected current USB attachment on reconnect.
- Dante USB startup includes the native empty-transfer recovery timing.
- The mixer package includes the matching shared audio/MIDI runtime and
  control helper.

`components.lock.json` records the exact source revisions, package versions
and checksums.

## Devices and current qualification

Development hardware is Fireface UFX+, original Babyface and Digiface Dante.
Recognition of another profile is not proof of its complete hardware support.
Corrections are shared where relevant; hardware-specific capabilities are
not copied between unrelated families.

The software CI uses isolated local Linux VMs for the private component
repositories. Mint and Fedora archive/lifecycle checks are also run locally
inside the VM; the public distribution retains its hosted GitHub checks.
No USB controller or audio interface is passed into a CI VM.

Retained live tests include UFX+ playback, simultaneous existing owners at
different sample rates, preserved UFX+ links and visible UFX+/Dante mixer
selection. Package and mock tests do not prove physical hotplug, power-cycle,
wake recovery or operation of every channel/rate combination. Subsequent Digiface Dante tests exercised stereo network reception and transmission at 48 kHz. The release CI runs without physical devices.

This is an alpha release. Keep a known-good version and avoid unattended use
in critical sessions. The three source/package/release identities are tracked
separately from what is currently installed or loaded on a machine.

## Audio, settings and mixer

After installation/module preparation, enable the shared manager for your
desktop account if it is not already enabled:

```sh
systemctl --user enable --now rme-native-devices.service
rme-driver-panel
oscmix-ufxplus
```

The settings panel configures the driver; it is not the driver itself.
PipeWire exposes enabled per-device groups and physical ports to qpwgraph and
DAWs. ALSA applications use the advertised named aliases; numeric card indices
are not stable identities. The mixer device selector changes the viewed device,
not the system audio destination or clock synchronization.

Multiple interfaces are independent clock domains unless physically synchronized.
Their availability in one PipeWire graph is not a claim of an ASIO-style
hardware-synchronous aggregate. High sample rates change active optical/MADI
channel counts according to each device's format.

## Kernel frontend and Fedora

The shared ALSA frontend is the small external `snd-rme-pcm` module, built by
DKMS. Matching headers for the actual running kernel are required. Secure Boot
policy is not bypassed.

Fedora requires the exact kernel-devel package for the selected kernel, including
the correct provider for custom/T2 kernels. After installation run:

```sh
sudo /usr/libexec/ufxplus-linux/fedora-admin
```

The Fedora adapter keeps the pinned USB access rule and common lifecycle guard.
It does not change the host's global DKMS configuration. Fresh installation
leaves boot images untouched; any required removal of an old RME module from
an existing image uses the checked atomic migration path. No automatic reboot,
USB reset or firmware update is performed. See
[Fedora qualification](docs/fedora-qualification.md) for limits.

## Remove or build

Close the mixer and stop its RME user services, then run
`./install.sh --uninstall` from the verified archive. Settings are backed up
and preserved. Active owners or a busy module prevent final removal.

The public repository vendors exact DEBs so the suite can be rebuilt without
access to private source repositories. It never fetches unpinned “latest” inputs.

```sh
./tools/build-bundle.sh dist
python3 tools/build-fedora-bundle.py --output dist-fedora
```

RPM assembly needs Fedora's build tools. See the
[joint release procedure](docs/joint-release.md), component source repositories
and their licenses for maintenance and source-build instructions.
