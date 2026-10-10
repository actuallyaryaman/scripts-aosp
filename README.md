# ROM maintainer tools

Build helpers and feature installers for OnePlus aston ROM checkouts. VoltageOS
is the default. Build commands can target other ROMs using the same device trees;
feature patches require compatible source layouts and revisions.

These tools do not sync the ROM, commit source changes, or flash a device.

## Layout

| Directory | Contents |
| --- | --- |
| `scripts/build/` | Protected build launcher, worker, checks and Btrfs swap helper |
| `scripts/telegram/` | Optional Telegram notifications and rclone uploads |
| `scripts/features/` | Camera, Separate App Sound, emoji and Lindroid installers |
| `maintainer/camera-port/` | Camera bundle generators, pinned patches and manifests |
| `docs/` | Setup, feature details, compatibility and maintenance guides |
| `tests/` | Standalone checks and ROM checkout regression tests |
| `scripts/maintenance/` | Publication and secret audit |

Local diagnostics and historical helpers are private and excluded from publication.

## Install and prerequisites

Clone or copy this toolkit anywhere. It can live at `ROM_ROOT/rom-tools` or outside
the checkout. Commands below run from the ROM source root and assume the toolkit
is in `rom-tools`; replace that path when it lives elsewhere.

Use Linux with Bash, Python 3.10+, Git, curl and the normal dependencies required by
your ROM. The protected build launcher also requires a working systemd user
session, cgroup v2, util-linux and Btrfs tooling. Its current guard requires the
64 GiB swapfile created by the swap helper. Swap management requires root and a
Btrfs filesystem. Feature-specific dependencies are in the linked guides.

## Build

```bash
bash rom-tools/scripts/build/swap.sh status
sudo bash rom-tools/scripts/build/swap.sh enable --root "$PWD"
bash rom-tools/scripts/build/build.sh check --root "$PWD"
bash rom-tools/scripts/build/build.sh configure --root "$PWD"
bash rom-tools/scripts/build/build.sh build --root "$PWD"
```

The root is selected by `--root`, then `ROM_ROOT`, then the current directory.
The launcher accepts `check`, `configure` or `build`; it saves logs and keeps
runtime files under `.local-build/` in the checkout.

For another ROM on the same device trees:

```bash
export ROM_ROOT="$PWD"
export ROM_LUNCH_TARGET='your_aston-release-userdebug'
export ROM_BUILD_TARGET='bacon'
bash /path/to/rom-tools/scripts/build/build.sh build
```

| Setting | Default | Purpose |
| --- | --- | --- |
| `ROM_ROOT` | Current directory | Checkout for build helpers and Telegram |
| `ROM_LUNCH_TARGET` | `voltage_aston-cp2a-userdebug` | Argument passed to `lunch` |
| `ROM_BUILD_TARGET` | `bacon` | One target passed to `m` |
| `TELEGRAM_BUILD_CONFIG` | `$ROM_ROOT/.telegram-build.json` | Private Telegram configuration |
| `ROM_UPLOAD_DESTINATION` | Unset; uploads skipped | rclone destination, such as `remote:builds/aston/` |
| `ROM_OTA_PREFIX` | `voltage-` | Expected OTA ZIP filename prefix; empty accepts any prefix |

The worker uses up to eight available CPUs and one high-memory job slot. It
checks free disk space and preserves the existing swap and build safety checks.
Read [build setup](docs/local-build.md) before using it.

## Feature installers

Run checks before applying. Explicit feature root arguments take precedence;
otherwise these installers use the current directory.

| Feature | Check or setup command | Guide |
| --- | --- | --- |
| OnePlus camera | `bash rom-tools/scripts/features/apply-aston-camera.sh --check --root .` | [Camera](docs/cameraport.md) |
| Separate App Sound | `bash rom-tools/scripts/features/apply-separate-app-sound.sh --check .` | [Separate App Sound](docs/separate-app-sound.md) |
| Emoji selection | `bash rom-tools/scripts/features/apply-emoji-selection.sh --check .` | [Emoji](docs/emoji-style.md) |
| Lindroid | `bash rom-tools/scripts/features/setup-lindroid.sh --check .` | [Lindroid](docs/lindroid.md) |

Camera and Lindroid target the aston/sm8550 trees. Framework patches must still
match your checkout. Emoji requires `packages/apps/Powerhub` and `vendor/voltage`;
this cleanup does not adapt it to another ROM's settings app. Incompatible inputs
must pass preflight before source changes occur.

The camera installer remains self-contained: copy its single script to another
host and run it with `--root`. See the [portability guide](docs/camera-portability.md).

## Optional notifications and uploads

```bash
python3 rom-tools/scripts/telegram/telegram-notify.py setup
source rom-tools/scripts/telegram/telegram-build.sh
# Optional: use a remote already configured privately in rclone.
export ROM_UPLOAD_DESTINATION='remote:builds/aston/'
tgbuild bash rom-tools/scripts/build/build.sh build --root "$PWD"
```

Telegram setup stores credentials with mode `600` outside the toolkit. Never
commit that config or rclone credentials. An unset upload destination skips
uploads. Notification or upload failures do not change the build exit code.
See [Telegram setup](docs/telegram-build.md).

## Tests and publishing

Run `python3 tests/toolkit_test.py` from the toolkit for standalone mocked checks.
Checkout regression tests and their prerequisites are listed in
[testing](docs/testing.md). No full Android build or flash is part of these checks.

Before publishing, run the [publication audit](docs/publishing.md). It checks the
exact public file set with Gitleaks and scans decoded feature bundles. Private
bugreports, archived helpers, credentials, logs and caches must remain excluded.

See the [script guide](docs/script-guide.md) for detailed modes and side effects,
and [camera maintenance](docs/camera-maintenance.md) for bundle generation.
Third-party notices and pinned upstream references remain with their source
files and feature guides; see [attribution](docs/attribution.md).
