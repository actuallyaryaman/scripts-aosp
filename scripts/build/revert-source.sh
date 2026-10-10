#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh" "$@"
python3 - "$base" <<'PY'
from pathlib import Path
import sys
base=Path(sys.argv[1])
source=base.parent/'build/soong/ui/build/soong.go'
backup=(base/'soong.go.original').read_bytes()
block=b'\t// Opt-in local memory tuning must survive the builder\'s env -i launch.\n\tif config.Environment().IsEnvTrue("SOONG_LOW_MEMORY") {\n\t\tinvocationEnv["GOGC"] = "25"\n\t\tinvocationEnv["GOMEMLIMIT"] = "6GiB"\n\t}\n'
current=source.read_bytes()
if current!=backup and current.replace(block,b'',1)!=backup:
    raise SystemExit('Additional source edits found; refusing overwrite')
source.write_bytes(backup)
print('Original Soong source restored.')
PY
