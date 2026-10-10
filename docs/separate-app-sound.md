# Separate App Sound

Original VoltageOS implementation of the documented Samsung-style setup: select apps,
choose one alternate Phone/Bluetooth output, and choose a different main output through
Sound > Media output. Example: music app selected for Bluetooth; main output Phone;
Instagram Reels use Phone while the music continues. The reverse setup is supported.

Initially disabled. Supports up to 16 current-user launchable apps with distinct UIDs,
and media/game/legacy-media playback over speaker + active Bluetooth A2DP. Work profiles,
shared UID apps, LE Audio, casting, wired/USB combinations and simultaneous Bluetooth
headsets are outside this version's qualified routing contract. App notifications,
alarms, assistant and communication audio are excluded. No playback recording,
media-projection service, root, network access or proprietary Samsung code is used.

Both outputs must differ. Settings retain selections while disconnected. Ordinary
Android noisy-device/focus handling resumes on disconnect; paused playback is not
restarted automatically. An app choosing to stop playback for reasons unrelated to
Android audio focus cannot be forced to continue by this feature.

## Architecture

AudioService owns per-full-user AtomicFile configuration and registered render policies.
Its hidden configuration interface requires MODIFY_AUDIO_ROUTING and the foreground
user. The feature-only native route flag is accepted from system_server alone.
A dedicated non-primary PCM mixer is reserved; its existing tracks are invalidated
for destination-specific recreation, and ordinary clients cannot use it.
If unavailable, policy registration fails and ordinary audio remains active.
Selected UID + media-usage criteria are conjunctive. Compressed requests cannot fall
through to the wrong output; direct-support queries disable offload for affected media
and incompatible existing tracks must recreate through normal player PCM fallback.
Calls/non-media focus remain shared; only cross-output media focus loss is skipped.
Normal same-output arbitration and the existing global multi-audio-focus preference
remain unchanged. Disabling reconciles the focus stack with the newest owner.

Volume retains existing device indexes, dose protections and Bluetooth absolute volume.
Foreground selected media controls the alternate device; other foreground media uses
main output. SystemUI's Bluetooth indicator follows that destination. No independent
per-app volume or complete SoundAssistant functionality is included.

## Patch script

From the ROM root, run `bash rom-tools/scripts/features/apply-separate-app-sound.sh --check .`, then
`bash rom-tools/scripts/features/apply-separate-app-sound.sh --apply .`. `--status` reports
current state; --reverse removes the unchanged bundle. Omitting an option defaults to --check.
All project/file checks complete before mutation. Unrelated dirty files are preserved;
affected-file edits, partial bundles and unsafe paths stop. No network, commits, sync,
index writes, builds, or flashing. Persistent transaction backups enable recovery.
--show-patch prints the embedded patches for review. Use no concurrent source writers.

The script accepts different clean source revisions when the complete embedded patch
applies by context. It tests application in temporary copies before changing the ROM;
the source need not match this checkout's original file hashes or permission bits.
Existing permissions such as `664` are preserved. On a different revision, all affected
files must be clean; unrelated local patches may remain. Genuine patch conflicts stop
with Git's file/hunk diagnostics, without applying a partial bundle. A successful patch
check does not establish Android API, compilation or hardware compatibility.

Each installation records its actual before/after hashes and applied modes in
`.local-build/separate-app-sound/transaction.json`. Keep this directory for safe reversal
and interrupted-transaction recovery. Later edits or permission changes to installed
files are protected. Copy the updated script to another server, then run `--check .`
followed by `--apply .`; no repository downloads are needed by this script.

## Build and automated verification

The maintainer always runs ROM builds and flashes personally. Agents and this script
must not start them. The commands below are instructions for the maintainer.

Use your existing voltage_aston-cp2a-userdebug build configuration:

    m Settings SystemUI services framework-minus-apex libaudiopolicymanagerdefault \
        AudioServiceTests audiopolicy_tests
    atest AudioServiceTests:com.android.server.audio.MediaFocusControlTest
    atest audiopolicy_tests:SeparateAppSoundMixTest

API methods/constants are hidden; only framework-internal Binder and native AIDL change.
Build all affected artifacts together; this is not an APK-only feature.
Run the bundled host transaction tests without building Android:

    python3 rom-tools/tests/separate_app_sound_bundle_test.py .
    python3 rom-tools/tests/separate_app_sound_volume_test.py .

Host bundle transaction tests cover clean revision differences, `664`/`600` baseline
permissions, genuine conflicts, apply/reapply/reverse, dirty-file rejection, unrelated
edit preservation, staged conflicts, partial state, and rollback after an injected
second-project apply failure. Android tests require the relevant device/test
runner; compiling a test does not demonstrate passing device behavior.

## Build failure fixed on 2026-10-08

The system API check failed with exit code 38 because
`AudioMix.ROUTE_FLAG_SEPARATE_APP_SOUND` appeared in the generated system API.
Its original comment put `@hide` after descriptive text on the same line.
The source and embedded patch now put `@hide` on its own Javadoc tag line.
API signature files remain unchanged.

Host patch checks and transaction tests pass. The maintainer must rerun the
build to confirm API generation and subsequent compilation pass. Resume the
same build command and output directory; no clean build is required for this
comment correction.

## Audio deadlock correction

The 2026-10-08 bug report confirmed a lock inversion in the original volume
lookup while switching Bluetooth audio devices. The corrected lookup reads an
atomic target snapshot and actual audio mode; playback and foreground queries
run asynchronously outside audio volume/settings locks. See the
[deadlock investigation and validation checklist](separate-app-sound-deadlock.md).
The corrected build still needs compilation and physical validation by the maintainer.

## Aston hardware qualification (required before shipping)

1. Bluetooth connected, music selected for Bluetooth, main output Phone: music and
   Instagram Reels must stay on separate outputs with no pause, fade or duck.
2. Reverse outputs: Instagram selected for Phone, main output Bluetooth.
3. Selected apps on the same output still follow normal focus arbitration unless the
   existing global multi-audio-focus option is enabled. Test transient media focus too.
4. Test phone/VoIP calls, alarm and assistant: both media outputs must follow ordinary
   interruption and focus restoration; communication routing must remain correct.
5. Test volume keys/sliders and Bluetooth hardware controls at low volume first.
   Verify speaker and Bluetooth indexes/indicator, absolute volume and safe-volume limits.
6. Test active playback when toggling, switching main output, switching active headset,
   disconnect/reconnect, changing selections, screen lock, app death and audioserver restart.
7. Check actual routing for offloaded music and an app setting a preferred device.
   Verify no encoded data is rendered as PCM and player fallback does not become silent.
8. Test multiple apps, reinstall/removal, full-user switching and permission denial.
9. With the feature off, verify ordinary speaker/Bluetooth/wired/USB/cast playback,
   alarms, notifications, accessibility, calls, capture restrictions and DRM media.
10. Check idle CPU/wakelocks and repeated dumpsys audio: no polling, leaked policy,
    stuck focus or new mixer while disabled. No phone numbers or Bluetooth addresses
    are added to feature diagnostic output.

Source application, compilation, automated-test execution and hardware qualification
are separate statuses. Do not advertise universal Samsung parity or device support
until the physical playback and interruption matrix passes.

Local documentation and host tests live in `rom-tools/`; reversing the feature
changes only ROM source files and retains these maintainer helpers.
