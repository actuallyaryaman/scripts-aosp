#!/usr/bin/env bash
# Convenience wrapper; copy apply-aston-camera.sh alone for a standalone installer.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$script_dir/apply-aston-camera.sh" --check "$@"
