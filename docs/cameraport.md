# Aston OnePlus Camera: installation and maintenance

## Working build

On **10 October 2026**, the maintainer completed the ROM build, flashed aston,
and reported that the camera works. The successful build log is
`build-logs/build-1791597166-1468950.log`; the source reports Android 17 / API 37.
This confirms the current integration builds and runs on the maintainer's device.
It does not claim that every camera mode or Gallery/editor feature was tested.

The installer supplies **OnePlus Camera, OnePlus Gallery and the bundled editor**.
Camera overrides `Camera2` and Lineage Aperture, so Aperture is excluded from the
product package selection. The port targets **aston only**.

## Install or reapply

From the ROM source root:

```bash
bash rom-tools/scripts/features/apply-aston-camera.sh --check
bash rom-tools/scripts/features/apply-aston-camera.sh --apply
```

Read the dry-run output before applying. A successful `--check` means source
patches are compatible; it can still report missing assets that `--apply` must
download. After applying, run `--check` again. An unchanged checkout should report
**0 files would change; 0 assets need download**. Build and flash yourself with
your usual commands.

After a completed `repo sync`, or after installing another mod:

```bash
bash rom-tools/scripts/features/apply-aston-camera.sh --check
bash rom-tools/scripts/features/apply-aston-camera.sh --apply
bash rom-tools/scripts/features/apply-aston-camera.sh --check
```

The script never runs `repo sync`. Stop if the first check reports source conflicts
or an unrecognized asset edit; resolve those before applying. Already-present
patches are skipped. Run sync, extraction and other patch installers sequentially.

## Another server

Copy **only `rom-tools/scripts/features/apply-aston-camera.sh`** to the same location on another server. The script contains its resolved source patches, new source files, package configuration and asset checksums. It does not require Separate App Sound, emoji selection, Lindroid, a local baseline file, the generator scripts, the temporary donor clone, or this server's build output. Bash, Python 3.9+, Git and curl are required. Downloads need access to GitLab.

Use a Linux build host with a writable compatible ROM checkout and enough space
for the changed assets, download cache and backups. No absolute path or executable
bit is required when invoking the script through Bash. For a different checkout
location, use `--root path/to/rom`; paths containing spaces must be quoted.

Portability applies to **compatible aston source/device/vendor trees with the
expected .1301 base or already-pinned camera assets**. Upstream camera patches
originate from AlphaDroid 16.2; this working integration is adapted to Android 17.
There is no requirement that source repository HEADs match this server, provided
the complete patch context still applies. Different Android APIs, overlapping
changes, or another firmware/blob set can require adapting the bundle.

**It cannot safely patch on top of any arbitrary change.** Compatible edits outside
the camera's patch context survive, including additions at the start/end of the
66 existing source files. Changes to required context, conflicting locally created
files, and unknown managed binary changes are refused. Passing a patch check alone
does not establish that a different ROM's combined behavior will work.

See the [portability audit](camera-portability.md) for the tested scenarios,
installer fingerprint and remaining limits.

## Modes

| Command | Effect |
| --- | --- |
| `--check` | Stages and checks source patches; verifies available assets; reports assets needing download. Does not download or change ROM source. |
| `--apply` | Stages source changes, downloads/verifies required pinned assets, saves backups, then applies. |
| `--status` | Reports the latest transaction and whether its files match the before/after states or have later edits. |
| `--show-patch` | Prints the resolved source diff for review. Binary asset changes are represented by the embedded checksum manifest. |
| `--reverse` | Restores files changed by the latest apply transaction. Refuses later edits to those files. |
| `--recover` | Restores a transaction left incomplete by a process/server interruption. |

The default root is the current directory. Use `--root relative/path` when running elsewhere. The `rom-tools/scripts/features/check-aston-camera.sh` wrapper calls the same dry run.

For offline input, supply pinned checkouts or directories with the same file layout:

```bash
bash rom-tools/scripts/features/apply-aston-camera.sh --check --donor path/to/vendor_oneplus_aston
bash rom-tools/scripts/features/apply-aston-camera.sh --apply \
  --donor path/to/vendor_oneplus_aston --package path/to/vendor_oplus_camera
```

`--donor` supplies device camera assets; `--package` supplies the app repository. Both are optional. Every file is verified regardless of its source. Existing matching ROM assets and verified download cache entries are reused. A missing app repository can be installed by the script. The script downloads individual files, never clones or fetches repositories. Upstream commits were downloaded as patches; their provenance is recorded in `camera-port/upstream.json`.

## Scope and pins

The donor is `vendor_oneplus_aston` at `49904d23ca16083fbf101c5a50e1eb451d6b45d8`; the camera package is `vendor_oplus_camera` at `d78f9c1fe4cfee562a298960c3bcabc86260aa6f`. The package installs at `vendor/oneplus/camera`.

The bundle carries 1,178 pinned `.400` camera assets, four private interface copies, and 151 package files. Only changed/missing assets are written. The rest of the `.1301` vendor tree, firmware, device identity and NFC fixups are retained. No astonc device or vendor repository is applied. Camera-only APS helper and super-resolution symlink definitions are adapted under aston.

The integration adds the required framework/native APIs, OPlus framework stubs, HDR metadata, isolated `libui_oplus`, camera policy, public-library exposure (merging the current common list), device wiring and extraction rules. Binder memory and camera teardown changes are gated for the port. Timestamp relaxation is controlled by the package's existing property. Non-camera hardware policy retains its original expansion. No global hidden-API environment override is installed.

The APS helper checks exact GNU ELF build IDs before using fixed offsets, publishes original function pointers before installing hooks, and uses the runtime page size. Unknown builds are left unhooked. Changing blobs requires updating the pins and reviewing this helper; do not remove the guard to accommodate a newer blob.

## Changes, backups and conflicts

The installer checks all source changes in a temporary isolated Git context before writing to the ROM. It does not commit, stage changes, reset repositories, run extraction, build, sync or flash. Existing unrelated source edits survive application, and Git indexes are unchanged. Unknown edits to managed binary assets are refused.

State is stored under `.local-build/aston-camera/`: downloaded assets, content-addressed backups, journal and previous transaction journals. Keep this directory if you need rollback. Each successful reapplication records a new transaction. After sync, `--reverse` restores the state immediately before the **latest** apply; it is not a complete uninstall across all historical syncs. If nothing changes, repeat apply retains the existing transaction.

An ordinary apply error or handled interrupt attempts rollback. After a hard
interruption, run:

```bash
bash rom-tools/scripts/features/apply-aston-camera.sh --status
bash rom-tools/scripts/features/apply-aston-camera.sh --recover
bash rom-tools/scripts/features/apply-aston-camera.sh --check
```

To undo the latest successful transaction, use
`bash rom-tools/scripts/features/apply-aston-camera.sh --reverse`. Recovery and reverse verify all
managed files and backups before restoring anything. If you edited a managed
file afterwards, resolve that edit first; the installer will not discard it.
A new server needs no old journal to install, but it cannot reverse transactions
performed on another server unless their backups and state were also transferred.

| Report | What to do |
| --- | --- |
| `Source conflicts` | Inspect the named file and `--show-patch`. Adapt the conflicting mod or camera patch; rerun `--check`. Do not reset the repo or force a patch. |
| `Unrecognized local asset edit` | Keep a copy and compare against the pinned source. Changing firmware/vendor blobs requires reviewing and updating the asset pins. |
| Download or checksum failure | Check network access and the pinned URL, or supply verified offline inputs. A Git LFS pointer is not the actual blob. |
| `Rollback blocked by later edit` | Preserve the later edit and reconcile it before retrying reversal. Do not delete backups to bypass the check. |
| `Another camera installer is running` | Let that installer finish; avoid concurrent source writers. |

The camera bundle and Separate App Sound touch different source files. Emoji selection and Lindroid are not prerequisites. Manual camera patches or earlier port implementations can conflict with this bundle. Run only one camera installer against a checkout at a time. Do not run `repo sync`, extraction, or another source-writing tool during application.

## Validation and remaining device checks

Host validation covered dry run, apply, repeat apply, source reset/reapply, reverse, recovery, conflict refusal, Git index preservation, a copied standalone script, clean source files without other mods, and an absent camera app directory. The Java stubs compiled against existing framework jars; the helper passed a host C++ syntax check. Non-camera policy parity was checked for all 18 migrated policy files, and build definitions were checked for all camera assets.

The maintainer's successful build and flash are recorded above. For a new checkout
or future update, test boot with enforcing SELinux, front/rear lenses,
portrait/night/burst, high zoom, HEIF/10-bit, video/HDR, Gallery/editor,
third-party camera access, and switching between Camera and Lens. Capture
logcat/tombstones for failures. These remain a regression checklist, not a list
of features the maintainer has individually confirmed.

To repeat the installer audit on a host with the pinned donor available:

```bash
python3 rom-tools/tests/aston_camera_portability_test.py
python3 rom-tools/tests/aston_camera_bundle_test.py --donor path/to/vendor_oneplus_aston
python3 rom-tools/tests/aston_camera_interface_test.py
python3 rom-tools/tests/aston_camera_private_elf_test.py
```

These checks use temporary fixtures and cached build outputs; they do not start
a ROM build, sync repositories or flash. The installer integration test's donor
argument is for the audit fixture only; ordinary installation needs no donor clone.

The generic ROM launcher icon map can override the camera's themed icon; launcher icon-map changes are intentionally left out of this camera installer.

`camera-port/prepare_bundle.py`, `finish_bundle.py`, `export_bundle.py`, baseline and reference manifests are maintainer/audit inputs, not runtime dependencies. `camera-port/resolved.patch` is the review copy of the embedded source diff. Regenerating a bundle requires reviewing its source baseline and pinned donor; routine users run the standalone installer above.

## Camera interface module-name correction

The first build stopped in Soong because a stock ODM camera AIDL prebuilt shared
a module name with the source-built system_ext interface. The corrected bundle
uses distinct `_odm` / `_vendor` module names for camera_rfi V1, cameraextension V1,
cammidasservice V1, sendextcamcmd V2 and the commondcs V1 ndk_platform compatibility library. Their module names avoid source/prebuilt substitution; the private ELF correction below also isolates conflicting installed filenames. Consumer dependencies, product packages and
extraction mappings use the distinct names. The installer can upgrade the original
bundle by reversing its affected hunks in staging before applying the correction.
No shared interface partition is changed. This correction is included in the
maintainer's successfully built and flashed integration.

The follow-up regression check scans explicit modules as well as generated AIDL names
throughout `hardware/oplus`, and verifies upgrades from both previous installer versions:

```bash
python3 rom-tools/tests/aston_camera_interface_test.py
```

## Private camera interface filenames

Soong configuration passed after the module-name fixes. Packaging then found three
duplicate output paths: cammidasservice V1 NDK and commondcs V1 ndk_platform in vendor,
and sendextcamcmd V2 NDK in ODM. Their stock AIDL hashes differ from the source interfaces,
so replacing the stock camera interfaces with source-built libraries was not assumed safe.

The installer keeps the stock camera interfaces under same-length private filenames:
`cammidasservice-C1-ndk`, `commondcs-C1-ndk_platform`, and `sendextcamcmd-C2-ndk`.
It updates only ELF `DT_SONAME` and `DT_NEEDED` strings, preserving file sizes, layout,
executable segments, symbols and interface hashes. Four renamed device interface copies
and their pinned consumers are supplied from verified stock inputs. The bundled system
sendextcamcmd copy and libcsextimpl are updated consistently. In total 26 ELF outputs
are transformed; the input and output SHA256 values are embedded in the installer.

Generated source libraries retain their existing filenames. Extraction reproduces the
private edits with `device/oneplus/aston/camera_private_libs.py`; explicit `MODULE` tags
retain the distinct Soong names when makefiles are regenerated. No patchelf installation
or dependency on another ROM feature is needed for the installer.

Host checks verify unchanged executable bytes and project the corrected filenames onto
the previous build's generated install rules to check for duplicate output paths:

```bash
python3 rom-tools/tests/aston_camera_private_elf_test.py
```

This projection checks the specific packaging failure without invoking a ROM build.
A future build still validates the full graph after any source changes.

## Camera platform SELinux domain

Camera is installed on `/product`, so its platform-private policy marks
`opluscamera_app` as `coredomain`. Three broad vendor-policy rules for generic
`vendor_data_file` and `vendor_default_prop` access are removed because they
conflict with platform-domain neverallows. Rules for specifically labeled camera
data, camera properties and HAL access remain.

Run `python3 rom-tools/tests/aston_camera_labeling_test.py` with the cached policy
and APK outputs from the labeling failure. It compiles temporary full and
platform-only policy candidates with neverallows enabled and runs all Treble
labeling tests. It writes no source, installed policy, or build stamp. Device
testing must still confirm the camera does not depend on the removed generic
permissions; any required access should use specific labels.

## Camera bootclasspath package check

The camera compatibility wrappers add `com.color.inner.content.res` and
`com.color.inner.view` to the existing `oplus-fwk` bootclasspath JAR. The installer
adds these two exact packages to the boot JAR allowlist, preserving its other
entries and keeping the check enabled. This fixes the package-check failure on
`ConfigurationWrapper`; `ViewWrapper` requires the second entry.

Run `python3 rom-tools/tests/aston_camera_bootjar_test.py` after a build has
produced the boot JARs. It checks all JARs from the recorded failed command using
temporary allowlists, reproduces the missing-entry failure, and verifies the
corrected check passes. It does not build Android or write a build stamp.

## 202504 SELinux compatibility entry

The port's system_ext public types `opluscamera_app` and `opluscamera_app_data_file`
are new relative to policy API 202504. Their camera-scoped
`sepolicy/private/compat/202504/202504.ignore.cil` entry records that they have no
older counterparts, matching the existing camera compatibility files for earlier APIs.
No allow rules, neverallows or compatibility checks are disabled. The failing cached
Treble host check was reproduced and passed with this entry in the combined mapping:

```bash
python3 rom-tools/tests/aston_camera_sepolicy_compat_test.py
```

This test uses policy outputs from your build and does not start a ROM build.
