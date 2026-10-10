# Aston camera installer portability audit

Audit date: **10 October 2026**. Commands run from the ROM source root.

## Verdict

The script is portable as a **single file across compatible aston checkouts and
Linux build hosts**. It carries its patches, package baselines, asset pins and ELF
rewrite helper. It does not require another mod, a fixed server path, the audit
tools, a donor clone, or an existing install journal.

It preserves compatible source edits and refuses overlapping edits or unknown
binary changes. It is not a universal merger for arbitrary ROMs, Android versions,
firmware versions, or changes to the same camera code. Always run `--check` after
sync or another mod and inspect the result before building.

Use the [installation and maintenance guide](cameraport.md) for commands,
offline inputs, recovery and device tests.

## Audited version

| Item | Value |
| --- | --- |
| Installer | `rom-tools/scripts/features/apply-aston-camera.sh` |
| Installer SHA256 | `89cf968e7c9911d7bd37d95e8479d2f97e5c476d8590e8c5a1138a5895089288` |
| Source/asset bundle ID | `88f4104ca16db6d954ac` |
| Source patches | 188; 66 existing files and 122 new files |
| Asset entries | 1,333, including package text files also covered by source patches |
| Donor pin | `49904d23ca16083fbf101c5a50e1eb451d6b45d8` |
| App-stack pin | `d78f9c1fe4cfee562a298960c3bcabc86260aa6f` |
| Audit host | Linux; Python 3.14.8; Git 2.56.0; curl 8.18.0 |
| Required runtime | Bash, Python 3.9+, Git, curl; Python standard library only |

The bundle ID describes source patches and assets. Runner-only changes can retain
that ID, so use the **whole-script SHA256** to identify the exact installer version.
The minimum Python version follows the APIs used; execution on Python 3.9 and
every other supported host version was not separately tested.

## Tests and results

| Scenario | Result / coverage |
| --- | --- |
| Current working checkout | Dry run: 0 source/asset changes; 0 downloads required. |
| Unrelated edits within patched files | Prefix and suffix additions preserved across all 66 existing files in source staging and full installer transactions; original patch context still checked. |
| Repeat with those edits | No changes; no duplicate append-only patch hunks. |
| Real overlaps | Native, camera service, framework, device configuration, camera policy and boot allowlist conflicts refused without source writes. |
| Conflicting new file | Unrecognized local content refused rather than overwritten. |
| Unknown binary edit | Refused before download or replacement. |
| Another path / copied script | Copied script alone, checkout/script names with spaces, relative script and `--root` paths pass. |
| Inherited Git environment | Invalid `GIT_DIR` and unrelated `GIT_WORK_TREE` do not redirect patch operations. |
| Compatible clean source HEADs | Check succeeds without Separate App Sound or font changes. This is a sparse fixture of the current repositories, not a different ROM build. |
| Missing app repository | Installed from embedded package text and pinned offline asset inputs. |
| Simulated sync | Restore patched source files, retain vendor assets, reapply successfully. No actual `repo sync` was run. |
| Rollback / recovery | Reverse restores the latest transaction; interrupted-state recovery succeeds; later edits block reversal. |
| Existing unrelated work | Sentinel source changes, public-library additions and Git index contents preserved. |
| Older installers | Supported legacy module-name patches upgrade in staging while preserving unrelated edits. |
| Download provenance | All 1,333 asset URLs use immutable per-file commit pins; no repository fetch. |
| Fresh network samples | One donor calibration file and the package `.gitattributes` downloaded afresh and matched their embedded SHA256. |
| Build/device evidence | Maintainer's build succeeded, device flashed, and camera reported working. Individual modes were not enumerated. |

The full cold download of all assets was not repeated on another physical server.
The tests use isolated temporary fixtures, verified local inputs and the existing
build outputs. Fresh network samples verify both pinned repositories were reachable
at audit time; continued network access and blob availability remain requirements.

## Portability corrections from this audit

The original runner treated some beginning/end-of-file hunks as fixed boundaries.
Harmless additions there caused conflicts even when all patch context matched.
The runner now permits boundary offsets with Git's `--unidiff-zero` option while
retaining every context and removal line in the embedded patches.

It checks whether the complete patch is already applied **before** attempting a
forward patch. This prevents append-only changes from being duplicated after an
unrelated boundary edit. Genuine mismatches still abort staging; no reject-file,
three-way or whitespace-ignoring fallback was added.

These changes affect the installer only. The camera source patches and asset
outputs match the successfully flashed bundle; the audit does not require another
ROM build or flash.

## Repeat the audit

```bash
sha256sum rom-tools/scripts/features/apply-aston-camera.sh
bash rom-tools/scripts/features/apply-aston-camera.sh --check
python3 rom-tools/tests/aston_camera_portability_test.py
python3 rom-tools/tests/aston_camera_bundle_test.py --donor path/to/vendor_oneplus_aston
python3 rom-tools/tests/aston_camera_interface_test.py
```

The first source audit needs the installed port's source files to reconstruct its
pre-port fixture. The integration audit also needs the exact donor files and
retained original inputs/backups for transformed ELF consumers. These are test
prerequisites, not dependencies of the standalone installer on a new server.

Changing an unrelated feature can preserve patch compatibility while still
changing behavior. Passing these host checks means application/recovery is tested;
build and device regression testing validate the combined ROM.
