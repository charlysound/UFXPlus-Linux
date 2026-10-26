# Fedora 44 experimental release qualification

Suite `0.1.0-alpha.3+devices.35` provides native Fedora 44 x86_64 RPMs,
revision `4.fc44`. The component releases remain pinned in
`components.lock.json`; the audio and GUI ELF payloads are unchanged.
The common Linux ALSA frontend has the explicit source compatibility patch
recorded in `packaging/fedora/patches/source.json`.

## Executed checks — 26 October 2026

The installed and exercised adapter source was
`4bd46c9062a9074e353064c6be82d359af45f3b4`. Publication adds the suite
version and documentation, and uses freshly built, checksum-verified assets.

- Fedora 44 x86_64, kernel `7.2.9-310.t2.fc44.x86_64`, external Babyface
  23314862 (USB `2a39:3fc7`), PipeWire 1.6.7 and SELinux enforcing.
- Thirteen archive and kernel lifecycle tests passed locally and on Fedora.
- Real RPM scriptlet install, upgrade, busy-removal refusal and final removal
  passed in a temporary chroot using an inert kernel-helper probe.
- Real DKMS removal and rebuilding passed on the Fedora machine; an active
  owner caused the real removal helper to refuse the operation.
- Only the target image containing the earlier desktop module was migrated.
  Other kernel images retained their SHA-256 values. All images were unchanged
  throughout the subsequent remove/rebuild cycle. The host DKMS configuration
  and default boot choice were unchanged.
- Babyface ALSA, kernel ALSA, PipeWire and MIDI reached their ready states.
  At 44,100 Hz the device exposed 10 capture and 12 playback channels.
- Simultaneous capture and silence playback ran for 30 seconds before the
  lifecycle fix and for 5 seconds after RPM4 installation, S32_LE,
  buffer 4096/period 1024, with zero client-reported xruns.
- Installed settings-panel and mixer windows rendered on isolated X11.
  Mixer pixels were checked with OpenGL and Cairo after allowing startup.

## Limits

This is an experimental, community distribution. These checks do not qualify
other Fedora releases, other card models on Fedora, Secure Boot enabled,
long-duration latency or stability, analog listening or physical loopback,
additional sample rates, unplug/replug, ALSA with PipeWire absent, a reboot
after the final image migration, or the full connected GUI interaction path.

An isolated Assign menu freeze was reported by the user and then cleared.
It has not been reproduced or diagnosed; do not describe it as a fixed GUI bug.
The offline mixer still emits a GTK adjustment warning and a restoration
warning at shutdown without a backend. Native TotalMix GUI parity is not claimed.

The test machine retains the older `7.0.10-201.t2.fc44.x86_64` default boot
entry as a fallback. Its exact development headers were unavailable and the
RME module is prepared for 7.2.9 only. Select the prepared kernel for RME audio.
The installer reports a default/running-kernel difference without changing
the default. No firmware or Class Compliant mode was changed.

The module is loaded after mounting the root filesystem. Fresh installations
do not need to rebuild an initramfs. Migration of an earlier image containing
the module preserves all unrelated modules, including its earlier ALSA
dependencies, validates dracut output, and replaces the image atomically.
The package's own DKMS calls suppress only their global post-transaction hook;
independent operating-system DKMS operations keep their administrator policy.

Use `./install.sh --uninstall` after stopping the RME services. Final host
RPM removal cleans its DKMS registrations and refuses an active owner or a
busy module. RPM upgrades do not run final-removal cleanup. User settings
are backed up and preserved.
