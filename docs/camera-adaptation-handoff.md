# Codex handoff: adapt the Aston camera installer after source sync

Updated **26 October 2026** for a Codex session on another server, with this toolkit
at `vos/rom-tools`. The user requests implementation: adapt the standalone camera
installer and its maintenance/tests to the receiving server's latest source trees.
Inspect that checkout and proceed with the implementation and host verification;
the repository states are discoverable inputs, not questions for the user.

Use the receiving checkout as the target. Keep implementation changes in
`rom-tools` and use disposable source fixtures for apply/reverse tests. Leave live
ROM source application, another sync, ROM builds and flashing to the maintainer
unless separately requested. This handoff does not start another agent or require
access to the originating chat, its local backups, or MemPalace.

## Start here on the receiving server

Run from the receiving `vos` root:

```bash
git -C rom-tools status --short
git -C rom-tools log -1 --oneline
sha256sum rom-tools/scripts/features/apply-aston-camera.sh
```

Read this document, [camera maintenance](camera-maintenance.md), and the applicable
project instructions. Inspect the installer and generator before running them.
Record affected repository HEADs and dirty/index states; preserve the user's work.
Capture the current camera preflight failure with
`bash rom-tools/scripts/features/apply-aston-camera.sh --check --root .`.
The check may write scratch/cache state but must leave ROM source unchanged.
If preflight already passes, verify the candidate and its coverage before deciding
whether a rebase is necessary. Resolve the actual current failures rather than
assuming the historical list below still applies.

## Current state and boundaries

- The original camera integration built successfully; the maintainer flashed it
  and reported a working camera. This remains historical evidence for the old base.
- On **25 October**, the user requested removal of the port from the originating
  local ROM tree. All seven installer transactions were reversed: 181 files
  restored and 139 installer-created files removed. All 188 source pre-images
  were verified; unrelated mods, toolkit, vendor camera repository and backups
  were retained. **Do not assume this rollback happened on the receiving server.**
- The original standalone installer remains available and unchanged as a reference.
  There is no completed post-sync camera rebase to reuse. Older documentation about
  installed files and test fixtures must be checked against the receiving checkout.
- Keep the scope **aston-only**, with OnePlus Camera, Gallery and editor. Preserve
  Camera's `Camera2`/Aperture overrides. Keep the existing `.400` camera donor and
  app-stack pins for this source rebase; a new blob set needs a separate review.
- Preserve Separate App Sound, font/emoji changes, newer device fixups, Dolby,
  face support and other unrelated source changes. Download required upstream
  commits as patches; avoid cloning or fetching entire source repositories.

## Goal and inputs

Adapt the approach behind `scripts/features/apply-aston-camera.sh` to the specified target trees and commit set. Produce a reviewed, standalone candidate that preserves unrelated target work and safely refuses incompatible changes.

Derive these inputs from the receiving checkout and record them in the delivery:

- Absolute target ROM root, product/device, Android version, firmware/vendor base.
- For each affected repository: path, current full HEAD, branch, dirty/index state, and whether an earlier camera port is installed.
- Existing pinned upstream repository URLs and full commit IDs, their order/dependencies, and intended camera behavior. Use the resolved release bundle as the starting reference rather than selecting a new port.
- Whether only source bases changed or the camera donor/app stack also changes. For changed assets, identify immutable donors, licenses/notices, file inventory and hashes.
- An isolated candidate directory under the target's `.local-build/`; deliver toolkit changes and a tested installer, without live installation in this task.

Treat the commit set as desired behavior to investigate. Some effects may already exist, have moved to another owner, or need a semantic adaptation on the new base.

## What the original adaptation did

The working installer embeds the **resolved final source changes**, new files, pinned asset manifest, Python runner and private ELF rewrite helper in one Bash file. Installing does not replay a remote cherry-pick sequence or depend on this maintainer checkout. The generation tools are separate maintainer machinery.

The original work staged upstream changes, explicitly merged incompatible framework/device/policy pieces, gated shared changes to aston, and exported reviewed before/after differences. It bundled matching `.400` camera assets into the otherwise `.1301` vendor integration, including Camera, Gallery and editor. It preserved unrelated features and supported preflight, idempotent application, transaction backups, reversal and interrupted-transaction recovery.

Compatibility depends on source context, API behavior and exact asset provenance. Matching repository HEADs is not required for compatible edits; new HEADs alone do not establish compatibility.

## Reference files

Paths below are relative to the receiving `rom-tools` checkout:

- `scripts/features/apply-aston-camera.sh`: released, self-contained installer and authoritative current embedded payload.
- `maintainer/camera-port/installer.py`: runner source; keep it consistent with the embedded runner.
- `maintainer/camera-port/{baseline.json,upstream.json,camera-blobs.json,previous-bundle.json}`: provenance and compatibility inputs.
- `maintainer/camera-port/{prepare_bundle.py,export_bundle.py,finish_bundle.py,prepare_private_camera.py,private_camera_elf.py}`: staging, export and private asset transformations.
- `docs/{cameraport.md,camera-maintenance.md,camera-portability.md}`: usage, generation and prior audit coverage.
- `tests/aston_camera_*_test.py`: source, portability, interface, ELF, boot-JAR and policy checks.

Read the relevant target project's instructions first. Preserve a copy of the original installer/manifests and record target states before bulk work. Keep scratch checkouts and backups outside Desktop folders.

## Adaptation sequence

1. **Audit first.** Inspect every affected repo and the pinned commits before editing. Map each requested effect to its current owner. Record already-present changes, genuine missing changes, conflicts, obsolete APIs and non-camera additions to preserve. Finish this step with a per-repo/commit compatibility table. Text sources need matching patch context, not globally identical file hashes; binary assets require expected or specifically approved hashes.

2. **Establish trustworthy pre-images in isolated staging.** Start from the target's intended source baseline, retaining unrelated local work. If a prior port is installed, remove only its attributable effects in staging after reviewing provenance. An already-patched live file is not a clean pre-image. Preserve the original baseline and legacy bundle separately. Use the original resolved payload as the semantic reference when rebasing the existing integration; inspect new upstream commits for any additional desired behavior.

3. **Merge the required behavior.** Build reviewed `before` and `after` trees. Preserve newer upstream logic while adapting API signatures, Binder/Parcelable layouts, module ownership, bootclasspath allowlists, extraction fixups and policy. For removed OPlus framework classes, search replacement APIs and callers before restoring compatibility classes. Compose dictionary/tuple extraction fixups without duplicate keys. Review both aston and non-aston policy branches and retain Dolby, face and other unrelated additions. A different product requires explicit product gating and a fresh compatibility assessment.

4. **Resolve assets separately.** Classify each existing managed asset as expected input, expected output, known legacy input or unknown content. Keep the original pinned donors when only source trees change. Approve replacement input hashes only after proving their provenance and transformation requirements. For a changed donor/app commit, regenerate and review the full inventory, paths, hashes, build references and ELF dependencies together. Retain APS build-ID checks and exact transformation input/output hashes; investigate unknown blobs rather than broadening allowlists to make preflight pass.

5. **Export a candidate from reviewed staging.** Update the maintainer machinery in an isolated checkout as needed. `prepare_bundle.py` contains assumptions about the original trees/patches and can require adaptation; running the original preparation command is not a generic rebase solution. `finish_bundle.py` and `prepare_private_camera.py` are preparation fragments, not standalone commands. Review the resolved diff, asset manifest, runner consistency, bundle ID and whole-script SHA256 before replacing any release file.

6. **Verify the exact candidate.** Add or use explicit candidate-path selection in the test harness. Existing tests commonly load the released installer relative to their own file; `ROM_ROOT` selects source trees and does not select a candidate script. Record which script and hashes each test used. Complete the acceptance checks below in isolated fixtures before proposing a live application.

## Historical failure checklist: verify against the target

The remote report from 22 October described seven context conflicts:

```text
device/oneplus/aston/Android.bp
device/oneplus/aston/extract-files.py
device/oneplus/sm8550-common/extract-files.py
hardware/oplus/sepolicy/qti/public/attributes
hardware/oplus/sepolicy/qti/vendor/file.te
hardware/oplus/sepolicy/qti/vendor/genfs_contexts
hardware/oplus/sepolicy/qti/vendor/vendor_qti_init_shell.te
```

It also reported eight removed classes under `hardware/oplus/oplus-fwk/src/`:

```text
android/app/OplusActivityManager.java
android/app/OplusWhiteListManager.java
android/hardware/camera2/IOplusCameraManager.java
android/hardware/camera2/OplusCameraManager.java
android/view/OplusWindowManager.java
com/oplus/app/OplusAppInfo.java
com/oplus/os/WaveformEffect.java
com/oplus/osense/OsenseResEventClient.java
```

For a source rebase, a staging-only `rebase_bundle.py` can recover each old
pre-image from the recorded baseline commit, verify `before_sha256`, apply the
resolved patch, and verify `after_sha256`. Those baseline pre-images were checked
successfully on the originating host for all 15 paths. If Git objects are missing,
obtain the exact referenced file/patch and verify it; do not guess the old content.
Restore a genuinely missing compatibility class from the **complete** post-image,
after searching for relocated/replacement implementations. Added diff lines alone
are not a complete class. Preserve exact methods, fields, invocation kinds and
Parcelable layouts; check duplicate classes and bootclasspath ownership. Retain
the reviewed haptics behavior in `WaveformEffect` and conservative feature stubs.

The old policy migration embeds entire file branches. Rebase against the current
content so new `dolby_dvs`, `oplus_face` and other additions survive both flag
states. Review `vendor_proc_camera` declarations, labels and consumers together:
the camera package already supplies its type, the original five proc labels and
an init-shell rule. Give each declaration/label one owner, preserve newly needed
rules, and prefer small conditional deltas over frozen copies of entire files.
Verify the camera-disabled expansion matches the new baseline.

When merging extraction scripts, compose fixups for paths already covered by a
tuple or dictionary key. Preserve existing fixup ordering, isolated `libui_oplus`,
APS linkage, private module mappings and final ELF rewrites. A repeated dictionary
key can silently discard another fixup. Run parsing/host fixture checks instead
of regenerating the live vendor tree.

The same report counted 14 unrecognized camera assets, 17 missing assets and 102
changed assets already accepted by historical hashes. Recompute these numbers.
Investigate each unrecognized file's actual bytes and provenance before approving
replacement with the pinned donor; adding `allowed_before` authorizes replacement,
not ABI compatibility. Keep `input_sha256`, output hashes and private rewrite
metadata unchanged for the pinned inputs, particularly `camera.qcom.so` and the
cammidasservice executable. Keep the matched Algo libraries and APS build-ID guards.

## Known regeneration trap

On 23 October, the reference installer was freshly inspected:

- SHA256: `89cf968e7c9911d7bd37d95e8479d2f97e5c476d8590e8c5a1138a5895089288`
- Embedded bundle: `864baa0dc2cc3e2c5009`; 188 source entries, 1,333 assets, 26 private ELF transformations.
- Donor: `49904d23ca16083fbf101c5a50e1eb451d6b45d8`; app stack: `d78f9c1fe4cfee562a298960c3bcabc86260aa6f`.

The checked-in `previous-bundle.json` contains only 1,329 assets, and `export_bundle.py` replaces its newly assembled asset list with that older list when it exists. Use the complete released manifest explicitly in adapted export machinery and review inventory differences by path and metadata. Keep legacy compatibility data independently. For this source-only rebase, retain all 1,333 asset entries and 26 transformations unless a reviewed change explains the difference. Source entry counts can change when current upstream already supplies an effect, but account for every original effect. Older documentation also lists a different bundle ID; identify the actual payload and whole-script hash directly.

Likely implementation locations: add the staging rebase entry point beside the
existing generators, adapt `export_bundle.py` to consume the explicit full release
manifest and reviewed replacement approvals, and add explicit candidate selection
to the camera tests. Update `camera-maintenance.md` with the reproducible new route.
Retain the original baseline and legacy source patches as versioned provenance;
do not silently overwrite them or claim all old/new base combinations are supported.

## Acceptance and delivery

Demonstrate on disposable fixtures:

- Clean target application; repeat application produces zero changes and no duplicate append-only hunks.
- Unrelated edits survive, including beginning/end additions in patched files and Git index contents.
- Genuine source overlaps, conflicting new files and unknown binaries fail before target writes.
- Reverse and interrupted recovery restore the recorded transaction; later edits block unsafe restoration.
- Standalone copied script works from another location, with spaces/relative paths, without maintainer files or unrelated mods.
- Offline pinned inputs verify correctly; source/API/module/ELF/bootclasspath/policy checks cover the adapted changes.

The source/test fixtures currently reconstruct originals by reversing the release
patch against installed files and may read original ELF inputs from local backups.
Those assumptions no longer hold on the rolled-back originating host and are not
guaranteed on the destination. Build fixtures from verified staging pre-images,
post-images and pinned inputs. Report missing prerequisites explicitly rather than
treating a fixture setup failure as a camera regression or weakening assertions.

Preserve the runner's complete-already-applied check before forward patching. The released runner supports boundary offsets using `--unidiff-zero` while retaining patch context; keep conflict refusal strict. Do not introduce reject-file or automatic three-way fallback into live installation.

Deliver the candidate installer, SHA256, resolved source diff, per-repo baseline/commit map, complete asset inventory/provenance, maintainer changes, and test results naming the exact candidate. Report source compatibility, asset readiness, compilation/policy validation and device behavior separately. A successful preflight can still report required asset downloads.

Before handing back the toolkit, run its standalone tests and bundle-aware
publication audit. Keep scratch files, credentials, build logs, backups and local
diagnostics outside the publishable file set. The maintainer will run the next ROM
build and flash. Give the exact root-relative preflight/apply commands for the
tested installer and list the remaining build/device checks. A dry run succeeding
is not a claim that the updated camera builds or works on device.

Completion means implemented toolkit changes, a reproducibly generated candidate
whose checks used that exact file, preserved unrelated work, documented unresolved
issues and a clear ready/not-ready decision. If a required API or blob provenance
cannot be resolved, identify the precise blocker rather than disabling a guard.
