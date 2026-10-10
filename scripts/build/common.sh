#!/usr/bin/env bash
# Shared checkout selection; source from build entrypoints.
helpers=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=${ROM_ROOT:-$PWD}
mode=
while (( $# )); do
    case "$1" in
        --root) [[ $# -ge 2 ]] || { echo '--root needs a path' >&2; exit 2; }; root=$2; shift 2 ;;
        --help|-h) echo "Usage: bash $0 [MODE] [--root ROM_ROOT]"; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; exit 2 ;;
        *) [[ -z "$mode" ]] || { echo 'Unexpected argument' >&2; exit 2; }; mode=$1; shift ;;
    esac
done
root=$(cd -- "$root" && pwd)
[[ -f "$root/build/envsetup.sh" ]] || { echo "Not a ROM checkout: $root" >&2; exit 1; }
export ROM_ROOT="$root"
base="$root/.local-build"
