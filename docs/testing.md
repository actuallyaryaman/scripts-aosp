# Testing

From the toolkit directory:

```bash
python3 tests/toolkit_test.py
python3 scripts/maintenance/publication_check.py --gitleaks
```

The standalone suite creates temporary checkouts, relocates the toolkit to a path
with spaces, mocks systemd/Telegram/rclone, and checks configuration propagation,
output conflicts, exit codes, config permissions, unsupported layouts and audit
rejection. It does not build Android, upload files or contact Telegram.

For tests that read ROM source or cached outputs, set `ROM_ROOT` to the checkout:

```bash
export ROM_ROOT=/path/to/rom
python3 tests/aston_camera_interface_test.py
python3 tests/aston_camera_portability_test.py
python3 tests/aston_camera_private_elf_test.py
python3 tests/aston_camera_bundle_test.py --donor /path/to/vendor_oneplus_aston
python3 tests/separate_app_sound_bundle_test.py "$ROM_ROOT"
python3 tests/separate_app_sound_volume_test.py "$ROM_ROOT"
```

Camera bundle/ELF integration requires pinned vendor inputs and, for certain
already-transformed files, existing camera backups. Separate App Sound bundle
tests use Git HEAD files in the checkout; volume tests require patched production
sources and a host or bundled JDK. Fixture tests work on temporary copies.

`aston_camera_labeling_test.py`, `aston_camera_bootjar_test.py` and
`aston_camera_sepolicy_compat_test.py` additionally require the recorded build
failure commands or cached policy/build artifacts described in their source.
Missing inputs are prerequisite failures, not evidence of a regression.

All tests locate toolkit scripts independently of `ROM_ROOT`. Default checkout
selection for checkout tests is the current directory. Temporary build caches
are not publication files. Hardware behavior still requires manual build and
flash qualification.
