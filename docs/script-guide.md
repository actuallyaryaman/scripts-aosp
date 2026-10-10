# Script guide

Commands shown in the main [README](../README.md) assume execution from the ROM
root. The toolkit can be elsewhere; use its actual path. Build helpers accept
`--root`, then `ROM_ROOT`, then the current directory. Feature installers retain
their explicit root arguments and current-directory defaults.

| Script group | Commands and behavior | Detailed guide |
| --- | --- | --- |
| `scripts/build/build.sh` | `check`, `configure`, `build`; transient systemd service and checkout lock | [Build](local-build.md) |
| `scripts/build/worker.sh`, `guard.py` | Internal launcher helpers; lunch, build, disk monitoring and signal cleanup | [Build](local-build.md) |
| `scripts/build/swap.sh` | `status`, `enable`, `remove`; managed Btrfs swap, root needed for changes | [Build](local-build.md) |
| `scripts/build/revert-source.sh` | Legacy Soong-backup recovery; refuses unrelated edits | [Build](local-build.md) |
| `scripts/telegram/telegram-build.sh` | Source to define `tgbuild`; preserves the command's exit status | [Telegram](telegram-build.md) |
| `scripts/telegram/telegram-notify.py` | `setup`, `check`, `start`, `watch`, `finish`, `uploaded` | [Telegram](telegram-build.md) |
| `scripts/telegram/telegram-upload.py` | `ROM_ROOT BUILD_LOG`; validated OTA and images uploaded using rclone | [Telegram](telegram-build.md) |
| `scripts/features/apply-aston-camera.sh` | `--check`, `--apply`, `--status`, `--reverse`, `--recover`, `--show-patch`; explicit `--root` | [Camera](cameraport.md) |
| `scripts/features/check-aston-camera.sh` | Convenience wrapper for camera `--check` | [Camera portability](camera-portability.md) |
| `scripts/features/apply-separate-app-sound.sh` | `--check`, `--apply`, `--status`, `--reverse`, `--show-patch`, optional root | [Separate App Sound](separate-app-sound.md) |
| `scripts/features/apply-emoji-selection.sh` | `--check` for offline preflight; otherwise apply, optional root | [Emoji](emoji-style.md) |
| `scripts/features/setup-lindroid.sh` | `--check`, optional `--fix-fcm`, optional root; apply fetches pinned dependencies | [Lindroid](lindroid.md) |
| `scripts/maintenance/publication_check.py` | `--list`, `--gitleaks`, `--staged`, `--history` | [Publishing](publishing.md) |

Feature compatibility depends on source layout and patch context, not only device
identity. Run preflight first. Do not run feature installers while a build is
reading or modifying the same checkout. Preserve user changes before application.

Camera and Separate App Sound track transaction backups in `.local-build/`.
Use their own reverse/recovery commands rather than deleting backup data. Emoji
and Lindroid have different recovery semantics; read their guides before applying.

Uploads are optional and start only after a successful `tgbuild` command when
`ROM_UPLOAD_DESTINATION` is set. Artifacts are not snapshotted: wait for uploads
to finish before starting a build that rewrites the same output files.

Maintainer camera generators are separate from normal installation and require
explicit input/output paths; see [maintenance](camera-maintenance.md).
Tests are grouped by prerequisites in [testing](testing.md).
