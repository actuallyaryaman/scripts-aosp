# Protected local build

The launcher uses a transient systemd user service, a checkout-local lock,
logging, disk checks and signal handling. Linux, cgroup v2 and a systemd user
session are required. It does not change Soong source or impose memory limits.

Run from the ROM root, or pass `--root PATH`:

```bash
sudo bash rom-tools/scripts/build/swap.sh enable --root "$PWD"
bash rom-tools/scripts/build/build.sh check
bash rom-tools/scripts/build/build.sh configure
bash rom-tools/scripts/build/build.sh build
```

Swap enable requires Btrfs and creates a 64 GiB swapfile in a separate subvolume
under `.local-build/swap/`. Activation lasts until reboot. No fstab, zram or
persistent system settings are changed. The existing swap setup requires at
least 164 GiB free before creating its subvolume.

The guard requires this swapfile, normal build dependencies and the checkout's
bundled Perl, JDK and Clang. The bundled Perl may need a host compatibility
library; install packages appropriate to your distribution after inspecting
its missing-library error.

Defaults are `voltage_aston-cp2a-userdebug` and `m bacon`. Set
`ROM_LUNCH_TARGET` and `ROM_BUILD_TARGET` for another ROM. `--root` overrides
`ROM_ROOT`, which overrides the current directory. The worker uses up to eight
available CPUs and one high-memory job slot. The guard requires 100 GiB free
before starting and stops the worker below 20 GiB free. There is no guarantee
against host OOM or heavy swapping.

`configure` and `build` use `.local-build/out` through the source-relative
`local-build-out` symlink. Missing aliases are created; conflicting paths are
rejected. Existing `out/` is not replaced. Logs, locks, cache and temporary files
remain in `.local-build/`. The launcher prints a `systemctl --user stop` command
and stops the service on interruption.

With builds stopped, remove the managed swap with:

```bash
sudo bash rom-tools/scripts/build/swap.sh remove --root "$PWD"
```

Removal refuses an unsafe swapoff when available RAM is insufficient. Reboot,
then retry. Never delete an active swapfile. Removing `.local-build/out` deletes
build outputs; preserve it when cleaning local state.

`revert-source.sh` is a legacy recovery helper for checkouts with an existing
`.local-build/soong.go.original` backup. It refuses to overwrite unrelated source
edits. It is not required for normal setup or builds.
