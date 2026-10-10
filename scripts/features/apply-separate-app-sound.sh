#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 The VoltageOS Project
# Samsung-style Separate App Sound for compatible Android source checkouts.
# Embeds all original ROM feature code, Android tests and resources.
# No downloads, model packs, commits, index writes, sync, builds or flashing.
# Default --check. --apply/--reverse preserve unrelated edits and use scoped backups.
# --show-patch prints the complete embedded diff for review.
# Requires Bash, Git and Python 3 (standard library); do not run concurrent source writers.
# Hardware qualification is required before release; see rom-tools/docs/separate-app-sound.md.
set -euo pipefail
command -v python3 >/dev/null || { echo "Python 3 is required" >&2; exit 1; }
command -v git >/dev/null || { echo "Git is required" >&2; exit 1; }
python3 - "$@" <<'SEPARATE_APP_SOUND_PYTHON'
import base64
import copy
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import tempfile

BUNDLE_HASH = '31d46ee41beeb270c96017df107845de2d4500252d19721152e7fdbac11f4083'
PAYLOAD = '''
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
WpMulCGDNR79gar0xKgRCI5gEm23Pdgxmy3ba4NsgbGH5tCDurDaghSA2whUjgyeY9gra6D1kGor
Ha8KFVer8xwI5tbkZazoD9Ek5hr/8W+8YufebHl2J+Ox9ebN3WRt2TurjqzRzp98nr958+YJQ32e
7+/vP2m8H3+03jTrxba1j/92rB9//Dy3/oVFVs/62P9leH15e9Mbvj/vfhieX15eDd91T/8y7F6c
Da97F2e9a6sQayQf/z314z0McPDDD5akENZkbPFkrRX0N6Atljvx7el08c23lkxOVp5ruR5tftDk
hx8O0qd51h90z88vfx4Mr65773vX172z4VnvU/+0ZxXK3yvW27dWFZPYT/l80LvqXnfxV/fqaji4
vL04Cz6r7aWPiiF3hwVeff6MPbfwL/cqaO47fZCcQHKNtDJ9cd1fhvimh85618Ory/P+6V+tRjnW
4vS6f9O77ne5EZpbVbTYfmRy6/DSEDp3B5nHaYdeMg7XDr3QUatWi3VrH/9tiKPmzTczK/GB9Rte
0T+JQcdWuSifhLhzbFWKEhUMOHts1eiTxzwbkqYFTFtzWvtMcKd/lAHd9I8ImJ1qsWnt479tAUz9
38pbb1Zzy3gij7S2Dm4ai8c+PEzsw+FhAO7DXP0HzY/kzuQYIrl5h9rH6WMlv1PrepQ/5Xebufd9
iSvWcwvvumfDT93z297ekUAOAmOlXCM4VsqNDECmzz8FpmmQOdy1/3SYbgVICiB32YunwrRaKbYA
02oDPwKYHhzsQLUnvgUWzZrMwfPN7am1AXdTtEBqrPX9xg97xLlG0/libTl8RjCnUnSy8vm7yXpm
+1/eosdadbguWpvgtzSIhG1OCvKeUv+m3p3tPFh/ysMlFGP7EHxbyMNi5Lm+ijGsEiNUifAO1RKG
yeXFvprMXe/7zaIHojwcSWgFAIg3JtJ9A98r/8uQv3u7FZonhCERcvwi5gMQzxfpR5HvF+pMkPUX
6ozvTlB6nKmqmeADycEbbjydED1qvy9Vh29OnKlnry436+VmXaAtCfAavGhBazcLds63Xh2b75I9
uqv39Q7SeviT9V952LDIQaF/mSPvBAJ7s14oVvoYv/jOmxN/s1wuiGac8XO/sFe689bij4KAOxxo
ST6AS4QSEELi0/u+xGKBy4o1Bym6n9zdeytw75PFarJ+ALmy55b7MLdnE0duA72c2asHa8G7ULRG
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
aTyH3uPj/wOiBySR8H0BAA==
'''


PREFIX = 'Separate App Sound'

def fail(message):
    raise RuntimeError(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def run(command, **kw):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    if result.returncode:
        fail(result.stderr.decode(errors='replace').strip() or 'Command failed: '+command[0])
    return result.stdout

def safe_path(root, relative):
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts or not part.parts:
        fail('Unsafe bundle path: '+relative)
    target = root / part
    cursor = target
    while cursor != root:
        if cursor.is_symlink():
            fail('Symlink in affected path: '+relative)
        cursor = cursor.parent
    if target.exists() and not target.is_file():
        fail('Expected regular file: '+relative)
    return target

def current(root, item):
    path = safe_path(root, item['path'])
    return digest(path.read_bytes()) if path.exists() else None

def classify(root, payload):
    before = after = 0
    changed = []
    for item in payload['files']:
        value = current(root, item)
        if value == item['before']:
            before += 1
        elif value == item['after']:
            path = safe_path(root, item['path'])
            if 'applied_mode' in item and stat.S_IMODE(path.stat().st_mode) != item['applied_mode']:
                changed.append(item['path'])
            else:
                after += 1
        else:
            changed.append(item['path'])
    if changed:
        return 'modified', changed
    if before == len(payload['files']):
        return 'unapplied', []
    if after == len(payload['files']):
        return 'applied', []
    return 'partial', []

def inspect_projects(root, payload):
    for project in payload['patches']:
        path = root / project
        if path.is_symlink() or not path.is_dir():
            fail('Project missing or symlinked: '+project)
        toplevel = run(['git', '-C', str(path), 'rev-parse', '--show-toplevel']).decode().strip()
        if Path(toplevel).resolve() != path.resolve():
            fail('Not a standalone Git project: '+project)
        names = [item['relative'] for item in payload['files'] if item['project'] == project]
        staged = run(['git', '-C', str(path), 'diff', '--cached', '--name-only', '--', *names])
        if staged:
            fail('Staged changes in affected files of '+project)

def preflight(root, payload, reverse=False):
    inspect_projects(root, payload)
    for project, patch in payload['patches'].items():
        command = ['git', '-C', str(root/project), 'apply', '--check', '--whitespace=error']
        if reverse: command += ['--reverse']
        run(command, input=patch.encode())

def recorded_payload(payload, journal):
    # New journals record the context-specific hashes; old journals use the embedded baseline.
    if journal.get('bundle') != BUNDLE_HASH or 'files' not in journal:
        return payload
    files = journal['files']
    expected = {item['path']:item for item in payload['files']}
    if len(files) != len(expected) or {item['path'] for item in files} != set(expected):
        fail('Invalid transaction manifest; affected paths do not match this bundle')
    for item in files:
        original = expected[item['path']]
        if any(item.get(key) != original[key] for key in ('project', 'relative')):
            fail('Invalid transaction manifest: '+item['path'])
        for key in ('before', 'after'):
            value = item[key]
            if value is not None and (not isinstance(value, str) or len(value) != 64
                    or any(c not in '0123456789abcdef' for c in value)):
                fail('Invalid transaction hash: '+item['path'])
    result = copy.deepcopy(payload)
    result['files'] = files
    return result

def prepare_application(root, payload, require_clean=False):
    inspect_projects(root, payload)
    if require_clean:
        for project in payload['patches']:
            names = [item['relative'] for item in payload['files'] if item['project'] == project]
            dirty = run(['git', '--no-optional-locks', '-C', str(root/project), 'status', '--porcelain',
                    '--untracked-files=all', '--', *names])
            if dirty:
                fail('Affected files must be clean before adapting to another revision:\n'
                        +dirty.decode(errors='replace').strip())
    result = copy.deepcopy(payload)
    # Try the complete bundle against copies, including this server's umask and file modes.
    # No indexes, Git objects or source files in the ROM checkout are written.
    with tempfile.TemporaryDirectory(prefix='separate-app-sound-check-') as directory:
        scratch = Path(directory)
        for project in payload['patches']:
            destination = scratch/project
            destination.mkdir(parents=True)
            run(['git', 'init', '-q', str(destination)])
        for item in result['files']:
            source = safe_path(root, item['path'])
            content = source.read_bytes() if source.exists() else None
            item.pop('baseline_mode', None)
            item.pop('applied_mode', None)
            item['before'] = digest(content) if content is not None else None
            if content is not None:
                item['baseline_mode'] = stat.S_IMODE(source.stat().st_mode)
                write_file(scratch/item['path'], content, item['baseline_mode'])
        for project, patch in payload['patches'].items():
            command = ['git', '-C', str(scratch/project), 'apply', '--whitespace=error']
            run(command+['--check'], input=patch.encode())
            run(command, input=patch.encode())
        for item in result['files']:
            target = scratch/item['path']
            item['after'] = digest(target.read_bytes()) if target.exists() else None
            if target.exists():
                item['applied_mode'] = item.get('baseline_mode', stat.S_IMODE(target.stat().st_mode))
    return result

def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as file:
        json.dump(value, file)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def write_file(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,
            prefix='.'+path.name+'.separate-app-sound-', delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if temporary.exists(): temporary.unlink()


def recover(root, journal, payload):
    payload = recorded_payload(payload, journal)
    expected_files = {item['path']:item for item in payload['files']}
    originals = journal['originals']
    if len(originals) != len(expected_files) or {item['path'] for item in originals} != set(expected_files):
        fail('Invalid recovery journal; affected paths do not match this bundle')
    for item in originals:
        expected = expected_files[item['path']]
        original_hash = expected['after'] if journal['reverse'] else expected['before']
        written_hash = expected['before'] if journal['reverse'] else expected['after']
        content = base64.b64decode(item['content']) if item['content'] is not None else None
        if item['hash'] != original_hash or item['written'] != written_hash or (
                digest(content) if content is not None else None) != original_hash:
            fail('Invalid recovery journal; original hashes do not match this bundle')
    unsafe = []
    for item in originals:
        path = safe_path(root, item['path'])
        value = digest(path.read_bytes()) if path.exists() else None
        if value == item['hash']:
            if path.exists() and stat.S_IMODE(path.stat().st_mode) != item['mode']:
                unsafe.append(item['path'])
            continue
        # Only replace our exact bundle result, never a later user's edit.
        expected = item['written']
        if value != expected or (path.exists() and stat.S_IMODE(path.stat().st_mode)
                != item.get('written_mode', item['mode'])):
            unsafe.append(item['path'])
            continue
        if item['content'] is None:
            if path.exists(): path.unlink()
        else:
            write_file(path, base64.b64decode(item['content']), item['mode'])
    if unsafe:
        fail('Recovery needs review; backups retained. Modified files: '+', '.join(unsafe))
    journal['status'] = 'rolled_back'
    return journal


def transact(root, payload, cache, reverse):
    journal_path = cache/'transaction.json'
    originals = []
    for item in payload['files']:
        path = safe_path(root, item['path'])
        content = path.read_bytes() if path.exists() else None
        originals.append({'path':item['path'], 'hash':digest(content) if content is not None else None,
                'content':base64.b64encode(content).decode() if content is not None else None,
                'mode':stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644,
                'written_mode':item.get('baseline_mode' if reverse else 'applied_mode', item['mode']),
                'written':item['before'] if reverse else item['after']})
    journal = {'bundle':BUNDLE_HASH, 'status':'applying', 'reverse':reverse,
            'started':time.time(), 'originals':originals, 'files':payload['files']}
    write_json(journal_path, journal)
    try:
        for project, patch in payload['patches'].items():
            command=['git','-C',str(root/project),'apply','--whitespace=error']
            if reverse: command+=['--reverse']
            run(command,input=patch.encode())
            # git apply can normalize existing read/write bits. Preserve this installation's
            # original modes after each project, before proceeding to another project.
            for item in payload['files']:
                if item['project'] != project: continue
                path = safe_path(root, item['path'])
                if path.exists():
                    os.chmod(path, item.get('baseline_mode' if reverse else 'applied_mode', item['mode']))
        state, _ = classify(root,payload)
        if state != ('unapplied' if reverse else 'applied'):
            fail('Written files do not match the bundle')
        journal['status']='complete'
        write_json(journal_path,journal)
    except BaseException:
        journal=recover(root,journal,payload)
        write_json(journal_path,journal)
        print(PREFIX+': affected source files restored.',file=sys.stderr)
        raise


def main():
    options={'--check','--apply','--status','--reverse','--show-patch'}
    operation='--check'
    root_arg='.'
    seen_operation=seen_root=False
    for arg in sys.argv[1:]:
        if arg in ('--help','-h'):
            print('Usage: bash rom-tools/scripts/features/apply-separate-app-sound.sh [--check|--apply|--status|--reverse|--show-patch] [ROM_ROOT]')
            return 0
        if arg in options:
            if seen_operation: fail('Choose one operation')
            operation=arg;seen_operation=True
        elif arg.startswith('--'):
            fail('Unknown option: '+arg)
        else:
            if seen_root: fail('Only one ROM_ROOT is accepted')
            root_arg=arg;seen_root=True
    raw=gzip.decompress(base64.b64decode(PAYLOAD))
    if digest(raw)!=BUNDLE_HASH:fail('Embedded payload checksum failed')
    payload=json.loads(raw)
    if operation=='--show-patch':
        for project,patch in payload['patches'].items():
            print('# Project: '+project)
            print(patch,end='')
        return 0
    root=Path(root_arg).resolve(strict=True)
    if not (root/'.repo').is_dir():fail('ROM_ROOT must contain .repo')
    cache=root/'.local-build'/'separate-app-sound'
    journal_path=cache/'transaction.json'
    for path in (root/'.local-build',cache):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            fail('Unsafe transaction directory: '+str(path))
    if journal_path.is_symlink():fail('Unsafe transaction journal')
    interrupted=False
    if journal_path.exists():
        journal=json.loads(journal_path.read_text())
        payload=recorded_payload(payload,journal)
        interrupted=journal.get('status')=='applying'
    state,changed=classify(root,payload)
    if state=='modified' and not interrupted and operation in ('--check','--apply','--status'):
        payload=prepare_application(root,payload,require_clean=True)
        state,changed=classify(root,payload)
        print(PREFIX+': patches fit this clean source revision.')
    print(PREFIX+': '+state)
    if operation=='--status':
        for path in changed:print('  modified: '+path)
        return 0 if state in ('applied','unapplied') else 2
    if operation=='--check':
        if state not in ('applied','unapplied'):
            fail('Partial bundle or affected-file edits: '+', '.join(changed))
        preflight(root,payload,reverse=state=='applied')
        if state=='unapplied': prepare_application(root,payload)
        print(PREFIX+': all project and patch checks passed. No source changes made.')
        return 0
    # Do not write backup material through a redirected cache directory.
    for path in (root/'.local-build',cache):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            fail('Unsafe transaction directory: '+str(path))
    cache.mkdir(parents=True,exist_ok=True)
    lock=cache/'apply.lock'
    if lock.is_symlink():fail('Unsafe transaction lock')
    with lock.open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if journal_path.is_symlink():fail('Unsafe transaction journal')
        if journal_path.exists():
            journal=json.loads(journal_path.read_text())
            if journal.get('status')=='applying':
                if journal.get('bundle')!=BUNDLE_HASH:fail('Another bundle has an interrupted transaction')
                # Recovery is a scoped restoration of this bundle's interrupted work.
                journal=recover(root,journal,payload)
                write_json(journal_path,journal)
                print(PREFIX+': recovered interrupted transaction.')
        state,changed=classify(root,payload)
        desired='unapplied' if operation=='--reverse' else 'applied'
        if state==desired:
            print(PREFIX+': already '+desired+'; no source changes.')
            return 0
        expected='applied' if operation=='--reverse' else 'unapplied'
        if state!=expected:fail('Partial bundle or affected-file edits: '+', '.join(changed))
        preflight(root,payload,reverse=operation=='--reverse')
        if operation=='--apply': payload=prepare_application(root,payload)
        transact(root,payload,cache,operation=='--reverse')
        print(PREFIX+': '+desired+'. Build and physical device validation are separate steps.')
    return 0


def interrupt(signum, frame):
    raise KeyboardInterrupt('Interrupted')

signal.signal(signal.SIGTERM,interrupt)
try:
    sys.exit(main())
except (RuntimeError,OSError,ValueError,KeyboardInterrupt) as error:
    print(PREFIX+': '+str(error),file=sys.stderr)
    sys.exit(1)

SEPARATE_APP_SOUND_PYTHON
