#!/usr/bin/env python3
"""Validate the camera platform-domain correction using cached build outputs."""
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
import re
import shlex
import subprocess
import tempfile

ROOT = Path(os.environ.get('ROM_ROOT', '.')).resolve()
PRODUCT = ROOT / 'out/target/product/aston'
SEPOLICY = ROOT / 'vendor/oneplus/camera/sepolicy'
assert 'typeattribute opluscamera_app coredomain;' in (SEPOLICY / 'private/opluscamera_app.te').read_text()
vendor_source = (SEPOLICY / 'vendor/opluscamera_app.te').read_text()
assert not re.search(r'^allow opluscamera_app (vendor_data_file|vendor_default_prop):', vendor_source, re.M)
for label in ('vendor_oplus_camera_data_file', 'vendor_camera_update_data_file', 'vendor_camera_prop'):
    assert label in vendor_source, label

version = (PRODUCT / 'vendor/etc/selinux/plat_sepolicy_vers.txt').read_text().strip()
inputs = [PRODUCT / 'system/etc/selinux/plat_sepolicy.cil',
          PRODUCT / f'system/etc/selinux/mapping/{version}.cil',
          PRODUCT / 'system_ext/etc/selinux/system_ext_sepolicy.cil',
          PRODUCT / f'system_ext/etc/selinux/mapping/{version}.cil',
          PRODUCT / 'product/etc/selinux/product_sepolicy.cil',
          PRODUCT / f'product/etc/selinux/mapping/{version}.cil',
          PRODUCT / 'vendor/etc/selinux/plat_pub_versioned.cil',
          PRODUCT / 'vendor/etc/selinux/vendor_sepolicy.cil',
          PRODUCT / 'odm/etc/selinux/odm_sepolicy.cil',
          PRODUCT / f'system/etc/selinux/plat_sepolicy_genfs_{version}.cil']
inputs = [path for path in inputs if path.is_file()]
log = (ROOT / '.local-build/out/error.log').read_text()
marker = '(out/host/linux-x86/bin/treble_labeling_tests '
if marker not in log:
    raise SystemExit('Need the recorded Treble labeling command in out/error.log.')
args = ['out/host/linux-x86/bin/treble_labeling_tests'] + shlex.split(log.split(marker, 1)[1].split(' > out/', 1)[0])

def checked(command):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr

with tempfile.TemporaryDirectory(prefix='camera-labeling-test-') as directory:
    directory = Path(directory)
    ext_index = next(i for i, path in enumerate(inputs) if path.name == 'system_ext_sepolicy.cil')
    ext = directory / 'system_ext.cil'
    ext.write_text(inputs[ext_index].read_text() + '\n(typeattributeset coredomain (opluscamera_app))\n')
    inputs[ext_index] = ext
    vendor_index = next(i for i, path in enumerate(inputs) if path.name == 'vendor_sepolicy.cil')
    lines = inputs[vendor_index].read_text().splitlines()
    broad_rule = re.compile(r'\(allow opluscamera_app_' + re.escape(version) +
                            r' (vendor_data_file_' + re.escape(version) +
                            r'|vendor_default_prop_' + re.escape(version) + r') ')
    removed = [line for line in lines if broad_rule.match(line)]
    assert len(removed) in (0, 3), removed
    vendor = directory / 'vendor.cil'
    vendor.write_text('\n'.join(line for line in lines if line not in removed) + '\n')
    inputs[vendor_index] = vendor
    platform = [path for path in inputs if path.name not in
                ('vendor.cil', 'odm_sepolicy.cil', 'plat_pub_versioned.cil')]
    for name, policy_inputs in (('full', inputs), ('platform', platform)):
        checked(['out/host/linux-x86/bin/secilc', '-m', '-M', 'true', '-G', '-c', '30',
                 *map(str, policy_inputs), '-o', str(directory / name),
                 '-f', str(directory / (name + '.contexts'))])
        print(f'PASS: {name} policy compiles with neverallows enabled.', flush=True)
    args[args.index('--precompiled_sepolicy') + 1] = str(directory / 'full')
    args[args.index('--precompiled_sepolicy_without_vendor') + 1] = str(directory / 'platform')
    checked(args)
print('PASS: all Treble labeling tests; generic vendor grants removed; specific camera access retained.')
