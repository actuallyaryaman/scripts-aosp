#!/usr/bin/env python3
"""Exercise the built boot JAR checker without building Android or writing stamps."""
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]

ROOT = Path(os.environ.get('ROM_ROOT', '.')).resolve()
ALLOW = ROOT / 'build/soong/scripts/check_boot_jars/package_allowed_list.txt'
ENTRIES = [r'com\.color\.inner\.content\.res', r'com\.color\.inner\.view']
log = (ROOT / '.local-build/out/error.log').read_text()
commands = [line[9:] for line in log.splitlines()
            if line.startswith('Command: ') and 'check_boot_jars ' in line]
if not commands:
    raise SystemExit('Need the recorded check_boot_jars failure in out/error.log.')
args = shlex.split(commands[-1].split(' && touch ')[0])
assert Path(args[0]).name == 'check_boot_jars'
assert args[2] == str(ALLOW.relative_to(ROOT))
current = ALLOW.read_text()
for entry in ENTRIES:
    assert current.splitlines().count(entry) == 1, entry
pattern = re.compile('^(' + '|'.join(line.strip() for line in current.splitlines()
                     if line.strip() and not line.lstrip().startswith('#')) + ')$')
assert not pattern.fullmatch('com.color.unrelated')
assert not pattern.fullmatch('com.color.inner.view.extra')

with tempfile.TemporaryDirectory(prefix='camera-bootjar-test-') as directory:
    candidate = Path(directory) / 'allowlist.txt'
    # Both missing namespaces must independently fail, not just the first one.
    jar = next(value for value in args[3:] if '/oplus-fwk/' in value)
    for entry in ENTRIES:
        candidate.write_text('\n'.join(line for line in current.splitlines()
                                       if line != entry) + '\n')
        failed = subprocess.run([args[0], args[1], str(candidate), jar], cwd=ROOT,
                                capture_output=True, text=True)
        assert failed.returncode != 0, entry
        assert entry.replace('\\', '') in failed.stderr, failed.stderr
    candidate.write_text(current)
    args[2] = str(candidate)
    passed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stdout + passed.stderr
print(f'PASS: both missing entries reproduced; all {len(args) - 3} boot JARs pass; narrow package scope.')
