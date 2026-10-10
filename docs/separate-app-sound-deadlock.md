# Separate App Sound deadlock fix — 2026-10-08

## Confirmed failure

The local bug report retained two system-server ANR/pre-watchdog episodes,
around 12:52 and 20:58 on October 8. In both, the AudioService thread held
`mSettingsLock` and the volume-state lock while calling the feature's
`volumeDevice()` from `VolumeStreamState.setIndex()`.

That lookup called `AudioManager.getMode()`, which acquires the broker's
`mSetModeLock`. AudioDeviceBroker already held that lock and was waiting for
`mSettingsLock` during communication-route processing. The later episode's
broker stack included Bluetooth SCO active-device handling. The circular wait
blocked audio routing, notifications, input handling and SystemUI.

The maintainer's previous build connects the same earphones successfully.
The report establishes the deadlock; it does not prove the cause of every
later pairing failure. An unrelated Dolby service tombstone also exists in the
report and must not be mistaken for this Java lock cycle.

## Implementation

Volume lookup now reads an atomic cached target and AudioService's existing
atomic **actual audio mode**. It does not query AudioManager, ActivityManager,
playback state or process state, and it takes no controller/broker/volume lock.
The public mode-owner API is unchanged.

An audio playback callback and a dedicated UID process-state observer enqueue
cache refreshes on the existing audio handler. The handler queries selected
apps' active media playback and foreground state outside controller locks.
The same selected + actively playing media + `PROCESS_STATE_TOP` rule remains.
Registration occurs once per controller lifetime; there is no polling.

Distinct atomic snapshot tokens reject work started before an invalidation.
Configuration changes, user switches, routing callbacks, teardown and native
audio-server loss clear the override. Route generations prevent a refresh
for an obsolete configuration from publishing. Non-normal audio modes use
normal volume routing immediately, through the atomic mode read.

Observer/query errors fall back to normal volume selection. Reconciliation and
startup exceptions are contained. SystemUI falls back to its ordinary Bluetooth
indicator when the feature query fails. During callback processing, volume can
briefly use the main route until a fresh eligible target is published.

The native Bluetooth/audio-policy implementation is unchanged by this fix.
Disabling a setting on an older affected binary cannot resolve a deadlock that
has already blocked its audio handler; install the corrected build to validate.

## Verification and remaining qualification

Run these host checks from the ROM root; they do not build Android:

```bash
bash rom-tools/scripts/features/apply-separate-app-sound.sh --check .
python3 rom-tools/tests/separate_app_sound_volume_test.py .
python3 rom-tools/tests/separate_app_sound_bundle_test.py .
```

The volume host test compiles the production cache class against inert Android
type declarations, parses the integration Java sources, and exercises bounded
lock-order completion, mode gating, eligibility and stale-refresh rejection.
It does not validate Android Binder callbacks or the Qualcomm HAL.
The fixture transaction test covers the updated complete feature bundle.
Both host checks and the bundle compatibility check passed on this checkout
after the correction. Android compilation and instrumentation tests were not run.
The volume host test requires the feature source files to be applied; the
transaction test instead constructs independent applied/unapplied fixtures.

The Android service regression tests are embedded in the patch bundle. The
maintainer runs compilation and Android tests personally:

```bash
# After your usual envsetup/lunch:
m Settings SystemUI services framework-minus-apex AudioServiceTests
atest AudioServiceTests:com.android.server.audio.SeparateAppSoundVolumeStateTest
atest AudioServiceTests:com.android.server.audio.MediaFocusControlTest
```

On the corrected build, start at low volume and test in this order:

1. Feature off, no playback: connect speaker, connect earphones, switch between
   them, then disconnect/reconnect each. Verify UI and volume keys stay responsive.
2. Repeat with ordinary music playback, still with the feature off.
3. Feature on: selected Apple Music on Bluetooth, main output Phone, Instagram
   on Phone. Check both outputs and foreground app volume selection.
4. While playing, switch speaker to earphones and back; turn Bluetooth off/on;
   disable/re-enable the feature and change selected apps.
5. Move selected playback to the background, pause/resume, remove an app and
   test a full-user switch. No previous user's volume target may remain.
6. Exercise phone/VoIP calls and call exit, ensuring communication volume and
   SCO routing remain normal. Check audio-server restoration if your test setup
   supports it, followed by normal playback.
7. Collect a bug report if anything stalls; check for new system-server ANRs or
   watchdogs. Do not count host tests alone as physical qualification.

Acceptance requires responsive UI/volume controls, successful headset switching,
both original playback destinations working, and no recurrence of the lock cycle.
ROM compilation, Android test execution and physical qualification remain
maintainer-run. Preserve the existing bug report locally; it is not bundled or
published with the script.
