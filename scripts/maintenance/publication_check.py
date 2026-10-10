#!/usr/bin/env python3
"""Audit the exact public file set, including compressed feature payloads."""
import argparse
import base64
import gzip
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DIRS = {'scripts', 'docs', 'tests', 'maintainer', '.github'}
PUBLIC_FILES = {'README.md', '.gitignore', '.gitleaks.toml'}
PRIVATE_DIRS = {'archive', 'diagnostics', '__pycache__', '.git', '.local-build', 'build-logs'}
PATTERNS = {
    'Telegram token': re.compile(r'(?<!\w)\d{6,12}:[A-Za-z0-9_-]{30,50}'),
    'GitHub token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
    'AWS access ID': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'personal home path': re.compile(r'/(?:home|Users)/[A-Za-z0-9_.-]+'),
}


def eligible(path):
    parts = path.parts
    return (not any(p in PRIVATE_DIRS for p in parts)
            and (parts[0] in PUBLIC_DIRS or str(path) in PUBLIC_FILES)
            and path.suffix not in {'.pyc', '.zip', '.log'}
            and not path.name.startswith('.telegram-'))


def public_files():
    result = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if any(p in PRIVATE_DIRS for p in rel.parts):
            continue
        if path.is_symlink():
            raise RuntimeError(f'Symlink is not publishable: {rel}')
        if not path.is_file():
            continue
        if not eligible(rel):
            raise RuntimeError(f'Unexpected file in public folder: {rel}')
        if path.name in {'.env', 'credentials', 'id_rsa', 'id_ed25519'} or path.suffix in {'.pem', '.key', '.p12', '.jks'}:
            raise RuntimeError(f'Private file is not publishable: {rel}')
        result.append(path)
    return result


def decoded_units(path, text):
    units = [(str(path), text)]
    if '# CAMERA_PAYLOAD_BEGIN\n' in text and path.name == 'apply-aston-camera.sh':
        payload = text.split('# CAMERA_PAYLOAD_BEGIN\n', 1)[1].split('# CAMERA_PAYLOAD_END', 1)[0]
        raw = gzip.decompress(base64.b64decode(''.join(line[2:] for line in payload.splitlines())))
        bundle = json.loads(raw)
        units.append((str(path) + ':decoded', raw.decode()))
        for entry in bundle['sources']:
            if entry.get('package_base'):
                units.append((str(path) + ':' + entry['path'], base64.b64decode(entry['package_base']).decode()))
    if path.name == 'apply-separate-app-sound.sh':
        payload = re.search(r"PAYLOAD = '''\n(.*?)'''", text, re.S)
        if not payload:
            raise RuntimeError('Separate App Sound payload missing')
        units.append((str(path) + ':decoded', gzip.decompress(base64.b64decode(payload.group(1))).decode()))
    return units


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Print public file paths only')
    parser.add_argument('--gitleaks', action='store_true', help='Require Gitleaks on the public files and decoded payloads')
    parser.add_argument('--staged', action='store_true', help='Reject staged files outside the public set; audit staged bytes')
    parser.add_argument('--history', action='store_true', help='Also scan local Git history with Gitleaks')
    args = parser.parse_args()
    files = public_files()
    if args.list:
        print('\n'.join(str(p.relative_to(ROOT)) for p in files))
        return
    units = []
    for path in files:
        units.extend(decoded_units(path.relative_to(ROOT), path.read_text()))
    if args.staged:
        names = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z']).decode().split('\0')
        for name in filter(None, names):
            path = Path(name)
            if not eligible(path) or ROOT / path not in files:
                raise RuntimeError(f'Non-public staged file: {name}')
            mode = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--stage', '--', name]).decode().split()[0]
            if mode == '120000':
                raise RuntimeError(f'Staged symlink: {name}')
            data = subprocess.check_output(['git', '-C', str(ROOT), 'show', ':' + name]).decode()
            units.extend(decoded_units(path, data))
    findings = [(name, kind) for name, text in units for kind, pattern in PATTERNS.items() if pattern.search(text)]
    if findings:
        for name, kind in findings:
            print(f'FAIL: {name}: {kind}')
        raise RuntimeError('Publication scan found sensitive content; values withheld')
    if args.gitleaks or args.history:
        executable = shutil.which('gitleaks')
        if not executable:
            raise RuntimeError('Gitleaks is required; install it and rerun')
        with tempfile.TemporaryDirectory(prefix='rom-tools-audit-') as directory:
            scan = Path(directory) / 'files'
            scan.mkdir()
            for number, (_, text) in enumerate(units):
                (scan / f'{number:04d}.txt').write_text(text)
            report = Path(directory) / 'findings.json'
            result = subprocess.run([executable, 'dir', str(scan), '--config', str(ROOT / '.gitleaks.toml'), '--redact=100', '--no-banner', '--report-format', 'json', '--report-path', str(report)], capture_output=True, text=True)
            if result.returncode:
                if report.exists():
                    for finding in json.loads(report.read_text()):
                        index = int(Path(finding['File']).stem)
                        print(f"FAIL: {units[index][0]}: {finding['RuleID']}")
                raise RuntimeError('Gitleaks failed; secret values and scanner output withheld')
        if args.history:
            result = subprocess.run([executable, 'git', str(ROOT), '--config', str(ROOT / '.gitleaks.toml'), '--redact=100', '--no-banner'], capture_output=True)
            if result.returncode:
                raise RuntimeError('Git history scan failed; review privately with Gitleaks --redact=100')
    print(f'PASS: {len(files)} public files; {len(units)} text units including decoded payloads; no secret findings.')
    print('Excluded: local diagnostics, historical archive, bytecode, Git metadata and runtime data.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
