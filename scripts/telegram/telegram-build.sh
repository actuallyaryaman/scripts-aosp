#!/usr/bin/env bash
# Source this file after build/envsetup.sh to use tgbuild with m or brunch.

_TG_BUILD_HELPERS=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
_TG_BUILD_ROOT=$(cd -- "${ROM_ROOT:-$PWD}" && pwd) || return 1
export ROM_ROOT="$_TG_BUILD_ROOT"

tgbuild() (
    set +e
    if (( $# == 0 )); then
        echo 'Usage: tgbuild m bacon  OR  tgbuild brunch aston userdebug' >&2
        exit 2
    fi
    local helper="$_TG_BUILD_HELPERS/telegram-notify.py"
    local started label log result watcher= interrupted=0
    started=$(date +%s)
    label="$*"
    mkdir -p "$_TG_BUILD_ROOT/build-logs" || exit 1
    log="$_TG_BUILD_ROOT/build-logs/build-${started}-${BASHPID}.log"
    : > "$log" || exit 1
    trap 'interrupted=130' INT
    trap 'interrupted=143' TERM
    trap 'if [[ -n "$watcher" ]]; then kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null; fi' EXIT
    python3 "$helper" watch "$log" "$started" "$label" >> "$log.telegram.log" 2>&1 &
    watcher=$!
    "$@" 2>&1 | tee "$log"
    result=${PIPESTATUS[0]}
    (( interrupted == 0 )) || result=$interrupted
    kill "$watcher" 2>/dev/null
    wait "$watcher" 2>/dev/null
    watcher=
    nohup python3 "$helper" finish "$log" "$started" "$label" "$result" >> "$log.telegram.log" 2>&1 < /dev/null &
    if (( result == 0 )) && [[ -n "${ROM_UPLOAD_DESTINATION:-}" ]]; then
        nohup python3 "$_TG_BUILD_HELPERS/telegram-upload.py" "$_TG_BUILD_ROOT" "$log" >> "$log.upload.log" 2>&1 < /dev/null &
    fi
    if (( result == 0 )) && [[ -z "${ROM_UPLOAD_DESTINATION:-}" ]]; then
        echo "Upload skipped: ROM_UPLOAD_DESTINATION is unset."
    fi
    echo "Build log: $log"
    exit "$result"
)
