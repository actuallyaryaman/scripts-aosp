#!/usr/bin/env python3
"""Audit source portability in isolated copies; never modifies ROM source."""
import argparse
import hashlib
import importlib.util
import tempfile
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]

ROOT = Path(os.environ.get('ROM_ROOT', '.')).resolve()
spec = importlib.util.spec_from_file_location('camera_runner', TOOLS / 'maintainer/camera-port/installer.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
script = TOOLS / 'scripts/features/apply-aston-camera.sh'
bundle = runner.load_bundle(script)
assert (TOOLS / 'maintainer/camera-port/installer.py').read_text() in script.read_text()
for asset in bundle['assets']:
    origin = ('vendor_oneplus_aston', '49904d23ca16083fbf101c5a50e1eb451d6b45d8') if asset['origin'] == 'donor' else ('vendor_oplus_camera', 'd78f9c1fe4cfee562a298960c3bcabc86260aa6f')
    assert asset['url'].startswith('https://gitlab.com/alphadroid-project/' + origin[0] + '/-/raw/' + origin[1] + '/')
    assert len(asset['sha256']) == 64

def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}

def comments(path):
    suffix = Path(path).suffix
    if suffix == '.xml':
        return b'<!-- unrelated local prefix -->\n', b'\n<!-- unrelated local suffix -->\n'
    marker = b'//' if suffix in ('.bp', '.java', '.cpp', '.h', '.cc') else b';;' if suffix == '.cil' else b'#'
    return marker + b' unrelated local prefix\n', b'\n' + marker + b' unrelated local suffix\n'

with tempfile.TemporaryDirectory(prefix='camera portability ') as directory:
    directory = Path(directory)
    root = directory / 'different server ROM'
    root.mkdir()
    bases = {}
    for entry in bundle['sources']:
        if entry['before_sha256'] is None:
            continue
        path = root / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / entry['path']).read_bytes())
        ok, error = runner.patch(root, entry['patch'], reverse=True)
        assert ok, (entry['path'], error)
        bases[entry['path']] = path.read_bytes()
        prefix, suffix = comments(entry['path'])
        path.write_bytes(prefix + bases[entry['path']] + suffix)
    common = root / 'vendor/oneplus/sm8550-common/proprietary/vendor/etc/public.libraries.txt'
    common.parent.mkdir(parents=True, exist_ok=True)
    common.write_text('libunrelated_local.so\n')
    saved = snapshot(root)
    stage = directory / 'stage'
    stage.mkdir()
    changes = runner.source_stage(root, stage, bundle, {}, directory / 'cache', argparse.Namespace())
    assert snapshot(root) == saved
    for name in bases:
        prefix, suffix = comments(name)
        result = changes[name].read_bytes()
        assert result.startswith(prefix) and result.endswith(suffix), name
    for name, source in changes.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.read_bytes())
    assert 'libunrelated_local.so' in (root / 'device/oneplus/aston/configs/camera-public.libraries.txt').read_text()
    applied = snapshot(root)
    repeat = directory / 'repeat'
    repeat.mkdir()
    assert not runner.source_stage(root, repeat, bundle, {}, directory / 'cache', argparse.Namespace())
    assert snapshot(root) == applied
    print(f'PASS: boundary edits preserved across {len(bases)} existing files; repeat application is read-only.', flush=True)

    # Real overlap in each main subsystem must abort all source staging.
    targets = ['frameworks/native/libs/binder/ProcessState.cpp',
               'frameworks/av/services/camera/libcameraservice/CameraService.cpp',
               'frameworks/base/services/core/java/com/android/server/wm/ActivityStarter.java',
               'device/oneplus/aston/device.mk',
               'vendor/oneplus/camera/sepolicy/vendor/opluscamera_app.te',
               'build/soong/scripts/check_boot_jars/package_allowed_list.txt']
    for i, name in enumerate(targets):
        entry = next(item for item in bundle['sources'] if item['path'] == name)
        original = (root / name).read_bytes()
        base = bases[name].decode()
        # Pick a unique removal or context line; changing it breaks exact hunk matching.
        lines = entry['patch'].splitlines()
        candidates = [line[1:] for line in lines if line.startswith('-') and not line.startswith('---')]
        candidates += [line[1:] for line in lines if line.startswith(' ')]
        anchor = next(line for line in candidates if line.strip() and base.count(line + '\n') == 1)
        (root / name).write_text(base.replace(anchor + '\n', anchor + ' LOCAL_OVERLAP\n', 1))
        before = snapshot(root)
        failed_stage = directory / f'overlap-{i}'
        failed_stage.mkdir()
        try:
            runner.source_stage(root, failed_stage, bundle, {}, directory / 'cache', argparse.Namespace())
        except RuntimeError as error:
            assert 'Source conflicts' in str(error) and name in str(error), str(error)
        else:
            raise AssertionError('Overlapping edit unexpectedly accepted: ' + name)
        assert snapshot(root) == before
        (root / name).write_bytes(original)
    print('PASS: framework, native, device, camera policy and allowlist overlaps abort without source writes.', flush=True)

    new = next(entry for entry in bundle['sources'] if entry['before_sha256'] is None and not entry.get('merge_public_libraries'))
    path = root / new['path']
    original = path.read_bytes()
    path.write_text('Conflicting locally created file\n')
    before = snapshot(root)
    conflict = directory / 'new-file-conflict'
    conflict.mkdir()
    try:
        runner.source_stage(root, conflict, bundle, {}, directory / 'cache', argparse.Namespace())
    except RuntimeError as error:
        assert new['path'] in str(error)
    else:
        raise AssertionError('Unrecognized locally created file was accepted')
    assert before == snapshot(root)
    path.write_bytes(original)

    asset = next(entry for entry in bundle['assets'] if entry['path'] not in {item['path'] for item in bundle['sources']})
    path = root / asset['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'locally modified binary')
    try:
        runner.get_asset(asset, root, directory / 'cache', argparse.Namespace(donor=None, package=None))
    except RuntimeError as error:
        assert 'Unrecognized local asset edit' in str(error)
    else:
        raise AssertionError('Unrecognized binary was accepted')
    assert path.read_bytes() == b'locally modified binary'
    print('PASS: conflicting new files and unknown binary edits refused; pinned per-file download URLs audited.')
