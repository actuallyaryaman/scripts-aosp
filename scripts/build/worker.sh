#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh" "$@"
mode=${mode:-configure}
case "$mode" in configure|build) ;; *) echo "Expected configure or build" >&2; exit 2;; esac
cd "$root"
export OUT_DIR=local-build-out TMPDIR="$base/tmp"
export NINJA_HIGHMEM_NUM_JOBS=1
export CCACHE_DIR="$base/ccache" CCACHE_CONFIGPATH="$base/ccache.conf" CCACHE_DISABLE=1
mkdir -p "$TMPDIR" "$base/out"
if [[ -e "$root/local-build-out" || -L "$root/local-build-out" ]]; then
    [[ -L "$root/local-build-out" && $(readlink -f "$root/local-build-out") == "$base/out" ]] || {
        echo 'Conflicting local-build-out path; refusing to replace it.' >&2; exit 1;
    }
else
    ln -s .local-build/out "$root/local-build-out"
fi
source build/envsetup.sh
unset USE_CCACHE CCACHE_EXEC CC_WRAPPER CXX_WRAPPER
lunch "${ROM_LUNCH_TARGET:-voltage_aston-cp2a-userdebug}"
if [[ "${mode:-configure}" == build ]]; then m "${ROM_BUILD_TARGET:-bacon}"; fi
