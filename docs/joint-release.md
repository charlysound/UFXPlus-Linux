# Joint Mint22 / Fedora44 prerelease

Suite `0.1.0-alpha.6+multicard.1` publishes two installable archives under
one version,with a combined SHA256SUMS. The DEB archive targets Mint22.x and
Ubuntu24.04 amd64;the RPM archive targets Fedora44 x86_64.

## Source and payload contract

The driver and shared host packages are alpha26+release.1;TotalMixLike is
alpha82+release.1. The exact final commits,package versions,asset URLs,
runtime/control source inputs and hashes belong in `components.lock.json`.
Do not substitute a package from a different source or a CI-only GUI build.

The complete mixer package must contain the common audio/MIDI runtime and
matching control producer. `tools/verify-mixer-payload.py` checks its source
identity,ABI,manifest and every packaged runtime file. A host-only install
does not supply the bundled mixer runtime. Replacing files also does not
reload already-running services or helpers.

The Fedora adapter preserves the pinned USB access rule,the common kernel
frontend and the shared lifecycle guard. Unknown module source or unexpected
package overlap is rejected. Kernel preparation is explicit;there is no
automatic USB reset,firmware update,DSP profile replay or reboot.

## Release procedure

1. Review the exact driver/mixer source trees and retained qualifications.
   Run the offline workflow commands directly in disposable local VMs before
   any push or workflow request,without USB/audio/home passthrough. Transfer
   local Git bundles over SSH. Preserve failures and fix their causes;do not
   weaken numerical,ownership or device-safety assertions.
2. Build the legacy driver DEB,shared host DEB,complete runtime and mixer DEB
   from clean committed sources. Keep source archives,build inputs and hashes.
3. Pin those three packages in the lock and vendor their exact bytes. Source
   repositories remain private;the distribution can rebuild without private
   source credentials.
4. Run installer/unit checks and the real Mint/Fedora package lifecycle checks
   locally inside isolated VM containers. Public distribution GitHub checks
   remain hosted,not self-hosted runners exposed to untrusted pull requests.
5. Verify package identities,hashes,full mixer payload and both archive contents.
   Review combined integration before updating main without a force push.
6. Tag the exact published sources. A tag workflow stages a draft;publish only
   after required checks and downloadable assets have been verified.
7. Download release assets again,verify checksums,and record publication
   separately from local installation,activation and hardware qualification.

## Automated coverage and limits

Mint checks the actual signed Mint base-files package in a digest-pinned Mint22
image,installer OS gates,settings backups,explicit downgrade authorization,
corruption rejection,and dpkg installation/upgrade/removal hooks. The upgrade
baseline is a checksum-pinned previous public suite,read from a verified local
cache for direct local CI or downloaded by the published workflow.

Fedora builds native RPMs,checks identities and runs installation/upgrade/
failed-removal/final-removal in an isolated RPM chroot. Kernel-helper fixtures
are inert:these checks do not prove a real kernel module build,boot migration
or audio playback. Retained Fedora hardware evidence is dated separately in
[fedora-qualification.md](fedora-qualification.md).

Component tests include private D-Bus/Xvfb GTK sessions,exact UID/attachment
and completion guards,shared-runtime tests,and strict USB-boundary mutations.
The loopback image fixture uses the real nonzero allocation scale and checks
Cairo status;its exact pixel comparisons are unchanged. Menu scale tests wait
for allocation with the same expected geometry and tolerance.

No CI VM receives a physical card. Software checks do not establish physical
hotplug,power-cycle,wake,recovery latency,every channel/rate combination or
external Dante-network operation. The retained live Linux tests and the current
installed/loaded versions are distinct from this release's source/artifact CI.
