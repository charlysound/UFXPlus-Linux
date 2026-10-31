# Joint Mint 22 / Fedora 44 candidate

Suite `0.1.0-alpha.5+devices.35` delivers two architecture-specific archives
under one version. Use the DEB archive on Mint 22.x / Ubuntu 24.04 amd64 and
the RPM archive on Fedora 44 x86_64. Each includes its installer, exact component
lock and checksums. The release also has a combined `SHA256SUMS` for both archives.

## Shared implementation and source dependency

The host is `0.1.0~alpha.21+devices.35`; the mixer is
`0.2.0~alpha.67+commands.2`. The refreshed lock records the immutable component
tags, commits, asset URLs and checksums. OSCmix includes ARC preamp assignments,
paired Mic/Inst gain commands, Dynamics Gain 1–4, programmable F4–F8 actions and
safe USB protocol handover. The software test suite does not qualify physical
ARC buttons, LEDs, wheel behavior or native executed-pixel parity.

The UFX+ driver payload remains the established alpha.12 package and the shared
host is alpha.21; TotalMixLike advances from alpha.51 to alpha.67. Both archives
contain the same corrected common module C source and model-independent
owner/busy guards.
Fedora retains its separate, atomic dracut migration adapter. The common guard
is maintained in the driver repository; the distribution copy is checked
against the bytes in the pinned host DEB. Do not edit model-specific copies.
The mixer includes the audio/MIDI runtime at source `5a8c400` and control
producer at `fe6f4fe`, retained from the qualified alpha.66 installation.
The lock records their manifest and binary hashes. Both archive builders
verify the complete payload before packaging.
The Fedora RPM keeps the exact USB rule already shipped by the alpha.4 adapter, pinned as
`packaging/fedora/70-rme-native.rules`; it is not generated from alpha.67's
passive USB identity catalogue, which carries no permission policy.

## Automated checks

- TotalMixLike's private source repository uses local VM runners labelled
  `ubuntu-22.04` and `ubuntu-24.04` for its unchanged source regression matrix.
  Both VMs must be running before requesting a check. This avoids paid hosted
  compute while keeping the repository private and results visible on GitHub.
  The public distribution repository retains its standard GitHub-hosted CI.
- The Ubuntu build job constructs the Mint archive and checks installer OS
  gates (Mint 22, 22.1, 22.2, 22.3; reject 23), backups, rollback authorization,
  checksums and removal dispatch.
- A digest-pinned [Mint 22 image](https://hub.docker.com/r/linuxmintd/mint22-amd64)
  installs Mint's signed `base-files` package from its Mint repository, checks
  the resulting real os-release and archive preflight, then runs real dpkg
  fresh candidate installation, a real alpha.51 → alpha.67 upgrade from the
  checksum-pinned published alpha.4 suite, failed removal and final removal.
  DKMS is a fixture: this proves hook dispatch, source retention, diversion
  restoration and settings preservation, not a kernel build or hardware audio.
- Fedora 44 builds the RPMs, verifies their identity, exercises installation,
  upgrade and failed/final removal in an isolated RPM chroot. Its kernel helper
  is inert in that fixture. Unit tests cover image preservation and DKMS hooks.
- The supporting driver PR compiles the common module against Mint 22's Ubuntu
  24.04 kernel ABI and Fedora 44 headers, without loading it.
- Release staging rejects a missing target, corrupt inner checksums, a tag
  differing from the suite version, different component locks, or archives
  from another source commit. A failing target prevents release staging.

These container/chroot checks do not qualify boot, Secure Boot, desktop
interaction or an attached sound card. On 26 October 2026, a disposable Mint 22 Wilma VM (kernel 6.8.0-38-generic,
no USB/audio passthrough) passed the published host20 → candidate host21 upgrade,
real DKMS build/install and module load, a refused removal with a simulated
active runtime, full removal, fresh installation and reboot. DKMS registration,
package integrity and all four pre-existing XDG sentinels survived as expected.
The VM was powered off cleanly; the original backing disk was used read-only.
Evidence is in the development report. This is package/boot qualification in a
VM, not sound-card qualification. The earlier Fedora hardware qualification
belongs to RPM `4.fc44`; [its limits](fedora-qualification.md) remain applicable
and do not imply the new RPM `5.fc44` was installed on that machine.

## Delivery after review

1. Integrate the supporting driver PR, the TotalMixLike PR and this
   distribution PR after green checks. Keep each pinned source commit and the
   package input hashes.
2. On the reviewed distribution commit, create and push a tag equal to
   `v` plus `components.lock.json`'s suite version.
3. The tag workflow builds and tests both targets, then creates one **draft
   prerelease**, with exactly the two archives and their combined checksum file.
4. Review the draft's files and qualification notes, then publish it explicitly.
   Keep the existing alpha.4 assets intact and do not claim stable hardware support.

No new tag, merge or release publication is required merely to review this PR.
