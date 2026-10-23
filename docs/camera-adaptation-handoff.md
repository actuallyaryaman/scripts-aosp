# Handoff: adapt the Aston camera installer to different trees and commits

Prepared 23 October 2026. This is a portable engineering brief, not a dispatched task. The destination checkout and replacement commits have not been supplied. Fill in those inputs before implementation; this document does not authorize sync, live application, build, flash, commits, or publication.

## Goal and inputs

Adapt the approach behind `scripts/features/apply-aston-camera.sh` to the specified target trees and commit set. Produce a reviewed, standalone candidate that preserves unrelated target work and safely refuses incompatible changes.

Resolve these inputs with the user or supplied checkout:

- Absolute target ROM root, product/device, Android version, firmware/vendor base.
- For each affected repository: path, current full HEAD, branch, dirty/index state, and whether an earlier camera port is installed.
- Desired upstream repository URLs and full commit IDs, their order/dependencies, and intended camera behavior.
- Whether only source bases changed or the camera donor/app stack also changes. For changed assets, identify immutable donors, licenses/notices, file inventory and hashes.
- Output directory and whether work is limited to a candidate or includes later live installation.

Treat the commit set as desired behavior to investigate. Some effects may already exist, have moved to another owner, or need a semantic adaptation on the new base.

## What the original adaptation did

The working installer embeds the **resolved final source changes**, new files, pinned asset manifest, Python runner and private ELF rewrite helper in one Bash file. Installing does not replay a remote cherry-pick sequence or depend on this maintainer checkout. The generation tools are separate maintainer machinery.

The original work staged upstream changes, explicitly merged incompatible framework/device/policy pieces, gated shared changes to aston, and exported reviewed before/after differences. It bundled matching `.400` camera assets into the otherwise `.1301` vendor integration, including Camera, Gallery and editor. It preserved unrelated features and supported preflight, idempotent application, transaction backups, reversal and interrupted-transaction recovery.

Compatibility depends on source context, API behavior and exact asset provenance. Matching repository HEADs is not required for compatible edits; new HEADs alone do not establish compatibility.

## Reference files

Paths below are relative to the reference `rom-tools` checkout, currently at `/home/logic/Projects/aosp/vos/rom-tools`:

- `scripts/features/apply-aston-camera.sh`: released, self-contained installer and authoritative current embedded payload.
- `maintainer/camera-port/installer.py`: runner source; keep it consistent with the embedded runner.
- `maintainer/camera-port/{baseline.json,upstream.json,camera-blobs.json,previous-bundle.json}`: provenance and compatibility inputs.
- `maintainer/camera-port/{prepare_bundle.py,export_bundle.py,finish_bundle.py,prepare_private_camera.py,private_camera_elf.py}`: staging, export and private asset transformations.
- `docs/{cameraport.md,camera-maintenance.md,camera-portability.md}`: usage, generation and prior audit coverage.
- `tests/aston_camera_*_test.py`: source, portability, interface, ELF, boot-JAR and policy checks.

Read the relevant target project's instructions first. Preserve a copy of the original installer/manifests and record target states before bulk work. Keep scratch checkouts and backups outside Desktop folders.

## Adaptation sequence

1. **Audit first.** Inspect every affected repo and the supplied commits before editing. Map each requested effect to its current owner. Record already-present changes, genuine missing changes, conflicts, obsolete APIs and non-camera additions to preserve. Finish this step with a per-repo/commit compatibility table.

2. **Establish trustworthy pre-images in isolated staging.** Start from the target's intended source baseline, retaining unrelated local work. If a prior port is installed, remove only its attributable effects in staging after reviewing provenance. An already-patched live file is not a clean pre-image. Preserve the original baseline and legacy bundle separately. Use the original resolved payload as the semantic reference when rebasing the existing integration; inspect new upstream commits for any additional desired behavior.

3. **Merge the required behavior.** Build reviewed `before` and `after` trees. Preserve newer upstream logic while adapting API signatures, Binder/Parcelable layouts, module ownership, bootclasspath allowlists, extraction fixups and policy. For removed OPlus framework classes, search replacement APIs and callers before restoring compatibility classes. Compose dictionary/tuple extraction fixups without duplicate keys. Review both aston and non-aston policy branches and retain Dolby, face and other unrelated additions. A different product requires explicit product gating and a fresh compatibility assessment.

4. **Resolve assets separately.** Classify each existing managed asset as expected input, expected output, known legacy input or unknown content. Keep the original pinned donors when only source trees change. Approve replacement input hashes only after proving their provenance and transformation requirements. For a changed donor/app commit, regenerate and review the full inventory, paths, hashes, build references and ELF dependencies together. Retain APS build-ID checks and exact transformation input/output hashes; investigate unknown blobs rather than broadening allowlists to make preflight pass.

5. **Export a candidate from reviewed staging.** Update the maintainer machinery in an isolated checkout as needed. `prepare_bundle.py` contains assumptions about the original trees/patches and can require adaptation; running the original preparation command is not a generic rebase solution. `finish_bundle.py` and `prepare_private_camera.py` are preparation fragments, not standalone commands. Review the resolved diff, asset manifest, runner consistency, bundle ID and whole-script SHA256 before replacing any release file.

6. **Verify the exact candidate.** Add or use explicit candidate-path selection in the test harness. Existing tests commonly load the released installer relative to their own file; `ROM_ROOT` selects source trees and does not select a candidate script. Record which script and hashes each test used. Complete the acceptance checks below in isolated fixtures before proposing a live application.

## Known regeneration trap

On 23 October, the reference installer was freshly inspected:

- SHA256: `89cf968e7c9911d7bd37d95e8479d2f97e5c476d8590e8c5a1138a5895089288`
- Embedded bundle: `864baa0dc2cc3e2c5009`; 188 source entries, 1,333 assets, 26 private ELF transformations.
- Donor: `49904d23ca16083fbf101c5a50e1eb451d6b45d8`; app stack: `d78f9c1fe4cfee562a298960c3bcabc86260aa6f`.

The checked-in `previous-bundle.json` contains only 1,329 assets, and `export_bundle.py` replaces its newly assembled asset list with that older list when it exists. Use the complete released manifest explicitly in adapted export machinery and review inventory differences by path and metadata. Keep legacy compatibility data independently. These counts describe the reference, not a required count for a deliberately different feature set. Older documentation also lists a different bundle ID; identify the actual payload and whole-script hash directly.

## Acceptance and delivery

Demonstrate on disposable fixtures:

- Clean target application; repeat application produces zero changes and no duplicate append-only hunks.
- Unrelated edits survive, including beginning/end additions in patched files and Git index contents.
- Genuine source overlaps, conflicting new files and unknown binaries fail before target writes.
- Reverse and interrupted recovery restore the recorded transaction; later edits block unsafe restoration.
- Standalone copied script works from another location, with spaces/relative paths, without maintainer files or unrelated mods.
- Offline pinned inputs verify correctly; source/API/module/ELF/bootclasspath/policy checks cover the adapted changes.

Preserve the runner's complete-already-applied check before forward patching. The released runner supports boundary offsets using `--unidiff-zero` while retaining patch context; keep conflict refusal strict. Do not introduce reject-file or automatic three-way fallback into live installation.

Deliver the candidate installer, SHA256, resolved source diff, per-repo baseline/commit map, complete asset inventory/provenance, maintainer changes, and test results naming the exact candidate. Report source compatibility, asset readiness, compilation/policy validation and device behavior separately. A successful preflight can still report required asset downloads.

Historical evidence: the original port passed host tests and the maintainer reported a successful build/flash and working camera. That does not validate these new trees or every mode. The later remote post-sync diagnosis was advice only; no remote rebase/application/build was completed. Once authorized for a new target, build and test its Camera/Gallery/editor behavior and confirm other products remain unaffected where shared code changed.
