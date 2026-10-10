#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh" "$@"
mode=${mode:-check}
case "$mode" in check|configure|build) ;; *) echo 'Expected check, configure or build' >&2; exit 2;; esac
for tool in systemd-run systemctl flock python3 tee; do
    command -v "$tool" >/dev/null || { echo "Required command missing: $tool" >&2; exit 1; }
done
mkdir -p "$base/logs"
# Swap setup may create this lock as root. flock on Linux accepts a read FD.
if [[ ! -e "$base/build.lock" ]]; then : >"$base/build.lock"; fi
exec 9<"$base/build.lock"
flock -n 9 || { echo 'Another build launcher is running.' >&2; exit 1; }
unit="vos-local-$(date +%s)-$$"
echo "Stop with: systemctl --user stop $unit.service"
trap 'systemctl --user stop "$unit.service" >/dev/null 2>&1 || true' EXIT
systemd-run --user --wait --pipe --collect --unit="$unit" \
 -p MemoryAccounting=yes -p TasksMax=2048 -p Nice=10 \
 -p KillMode=control-group -p TimeoutStopSec=10s \
 /usr/bin/env -i HOME="$HOME" USER="$(id -un)" LOGNAME="$(id -un)" \
 PATH=/usr/bin:/bin LANG=C.UTF-8 \
 ROM_ROOT="$root" ROM_LUNCH_TARGET="${ROM_LUNCH_TARGET:-voltage_aston-cp2a-userdebug}" \
 ROM_BUILD_TARGET="${ROM_BUILD_TARGET:-bacon}" \
 /usr/bin/python3 "$helpers/guard.py" "$mode" 2>&1 | tee "$base/logs/$unit.log"
