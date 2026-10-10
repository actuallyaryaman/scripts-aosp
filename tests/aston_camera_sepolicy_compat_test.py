#!/usr/bin/env python3
"""Run the existing Treble host checker against cached CIL inputs, without building Android."""
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
import subprocess,tempfile
ROOT=Path(os.environ.get('ROM_ROOT', '.')).resolve()
BASE=ROOT/'.local-build/out/soong/.intermediates/system/sepolicy'
exe=BASE/'tests/treble_sepolicy_tests/linux_glibc_x86_64/treble_sepolicy_tests'
mapping=BASE/'treble_sepolicy_tests_for_release/202504_mapping.combined.cil/android_common/gen/202504_mapping.combined.cil'
current=BASE/'base_product_pub_policy.cil/android_common/aston/base_product_pub_policy.cil'
old=BASE/'prebuilts/api/202504/202504_plat_pub_policy.cil/android_common/202504_plat_pub_policy.cil'
ignore=ROOT/'vendor/oneplus/camera/sepolicy/private/compat/202504/202504.ignore.cil'
for p in (exe,mapping,current,old,ignore):
 if not p.is_file():raise SystemExit('Required cached policy input missing: '+str(p))
args=[str(exe),'-b',str(current),'-m',str(mapping),'-o',str(old)]
result=subprocess.run(args,capture_output=True,text=True)
if result.returncode:
 assert 'opluscamera_app' in result.stdout+result.stderr and 'opluscamera_app_data_file' in result.stdout+result.stderr,result.stdout+result.stderr
 print('Reproduced the cached 202504 compatibility failure.')
with tempfile.TemporaryDirectory(prefix='aston-camera-policy-') as d:
 fixed=Path(d)/'202504_mapping.corrected.cil';fixed.write_text(mapping.read_text()+'\n'+ignore.read_text())
 args[4]=str(fixed);result=subprocess.run(args,capture_output=True,text=True)
 assert result.returncode==0,result.stdout+result.stderr
print('PASS: existing Treble checker accepts the 202504 camera compatibility entries.')
