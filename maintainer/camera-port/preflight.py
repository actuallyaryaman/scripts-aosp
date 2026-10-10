#!/usr/bin/env python3
"""Qualify inputs for the aston-only camera integration; never modify source."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


def safe_path(root, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or not part.parts or any(p in ('..', '.') for p in part.parts):
        raise ValueError(f'Unsafe manifest path: {relative}')
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes input directory: {relative}')
    return result


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_patches(directory):
    manifest = json.loads((directory / 'upstream.json').read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported upstream manifest schema')
    for entry in manifest['patches']:
        patch = safe_path(directory, entry['file'])
        if digest(patch) != entry['sha256']:
            raise ValueError(f'Patch checksum mismatch: {entry["file"]}')
        first = patch.read_text().splitlines()[0].split()
        if first[:1] != ['From'] or first[1] != entry['commit']:
            raise ValueError(f'Patch identity mismatch: {entry["file"]}')
    return manifest['patches']


def check_blobs(source, entries):
    """Accept documented stock or post-fixup bytes, never unverified substitutes."""
    missing, mismatched, verified = [], [], []
    for entry in entries:
        candidates = list(dict.fromkeys((entry['source'], entry['destination'])))
        found = [safe_path(source, name) for name in candidates
                 if safe_path(source, name).is_file()]
        match = None
        for path in found:
            value = digest(path, 'sha1')
            if value in entry['sha1']:
                match = {'destination': entry['destination'],
                         'input': str(path.relative_to(source.resolve())),
                         'sha1': value,
                         'state': 'stock' if value == entry['sha1'][0] else 'post-fixup'}
                break
        if match:
            verified.append(match)
        elif found:
            mismatched.append(entry['destination'])
        else:
            missing.append(entry['source'])
    return {'verified': verified, 'missing': missing, 'mismatched': mismatched}


def checkout_drift(root, baseline):
    changes = []
    for repo, revision in baseline['heads'].items():
        current = subprocess.run(['git', '-C', str(safe_path(root, repo)),
                                  'rev-parse', 'HEAD'], check=True,
                                 capture_output=True, text=True).stdout.strip()
        if current != revision:
            changes.append(f'{repo}: HEAD changed')
    for name, expected in baseline['files'].items():
        path = safe_path(root, name)
        actual = digest(path) if path.is_file() else None
        if actual != expected:
            changes.append(name)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.', help='ROM source root')
    parser.add_argument('--blobs', type=Path,
                        help='.400 dump root or Alpha proprietary directory')
    parser.add_argument('--json', action='store_true', help='Print a JSON report to stdout')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    directory = Path(__file__).resolve().parent
    entries = validate_patches(directory)
    baseline = json.loads((directory / 'baseline.json').read_text())
    blob_manifest = json.loads((directory / 'camera-blobs.json').read_text())
    blockers = []
    drift = checkout_drift(root, baseline)
    if drift:
        blockers.append('Checkout differs from the reviewed baseline; repeat the dry run.')
    package = root / 'vendor/oneplus/camera'
    package_errors = []
    for name, expected in baseline['camera_package'].items():
        path = safe_path(package, name)
        if not path.is_file() or digest(path) != expected:
            package_errors.append(name)
    if package_errors:
        blockers.append('Camera package differs from the reviewed snapshot.')
    blobs = None
    if args.blobs is None:
        blockers.append('Matching .400 camera blobs have not been supplied; use --blobs PATH.')
    else:
        source = args.blobs.resolve()
        if not source.is_dir():
            raise ValueError(f'Blob source is not a directory: {source}')
        blobs = check_blobs(source, blob_manifest['files'])
        if blobs['missing'] or blobs['mismatched']:
            blockers.append('The .400 blob source is missing files or has incorrect hashes.')
    # Blob readiness does not imply the reviewed raw patches form an applyable bundle.
    blockers.append('Resolved, gated integration bundle is not yet prepared; raw upstream patches must not be applied directly.')
    report = {'target': 'aston', 'camera_package_commit': baseline['camera_package_commit'],
              'patches_verified': len(entries),
              'reference_camera_files': len(blob_manifest['files']),
              'checkout_drift': drift, 'package_errors': package_errors,
              'blobs': blobs, 'ready_to_apply': False, 'blockers': blockers}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f'Aston camera preflight: {len(entries)} pinned patches verified.')
        print(f'Reference camera manifest: {len(blob_manifest["files"])} pinned files.')
        if blobs:
            print(f'Blobs: {len(blobs["verified"])} verified, '
                  f'{len(blobs["missing"])} missing, {len(blobs["mismatched"])} mismatched.')
            for label in ('missing', 'mismatched'):
                for name in blobs[label][:8]:
                    print(f'  {label}: {name}')
        for blocker in blockers:
            print('BLOCKED: ' + blocker)
        for name in (drift + package_errors)[:8]:
            print('  changed: ' + name)
        print('No source, index, blobs or build output changed.')
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Preflight failed: {error}', file=sys.stderr)
        sys.exit(2)
