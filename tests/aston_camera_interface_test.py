#!/usr/bin/env python3
"""Check stock/source module collisions and upgrades without running a ROM build."""
import ast,importlib.util,re,tempfile,argparse
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('ROM_ROOT', '.')).resolve()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
runner=module('runner',TOOLS/'maintainer/camera-port/installer.py')
fix=module('fix',TOOLS/'maintainer/camera-port/fix_camera_interface_names.py')
bundle=runner.load_bundle(TOOLS/'scripts/features/apply-aston-camera.sh')
bp=(ROOT/'vendor/oneplus/aston/Android.bp').read_text();mk=(ROOT/'vendor/oneplus/aston/aston-vendor.mk').read_text()
source=set()
for p in (ROOT/'hardware/oplus').rglob('Android.bp'):
 text=p.read_text();source.update(re.findall(r'\bname:\s*"([^"]+)"',text))
 for name in re.findall(r'aidl_interface\s*\{\s*name:\s*"([^"]+)"',text):
  for version in range(1,15):source.update([f'{name}-V{version}-ndk',f'{name}-V{version}-cpp'])
assert not source.intersection(re.findall(r'\bname:\s*"([^"]+)"',bp)), 'Stock vendor module still collides with OPlus source'
assert fix.fix_bp(bp)==bp and fix.fix_mk(mk)==mk
extract=(ROOT/'device/oneplus/aston/extract-files.py').read_text();assert fix.fix_extract(extract)==extract
parsed=ast.parse(extract);fn=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='lib_fixup_camera_partition');scope={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'fixup','exec'),scope)
for name,target in fix.RENAMES.items():
 for partition in ('vendor','odm'):
  assert scope['lib_fixup_camera_partition'](name,partition)==name+'_'+(target or partition)
 expected_stem=runner.PRIVATE_CAMERA_NAMES.get(name+'.so',name+'.so')[:-3]
 assert 'stem: "'+expected_stem+'"' in bp
 for partition in [target] if target else ['odm','vendor']:
  assert (ROOT/'vendor/oneplus/aston/proprietary'/partition/'lib64'/(name+'.so')).is_file()
# Every predecessor patch must upgrade successfully, even with unrelated edits in that file.
for old in bundle['legacy_sources']:
 with tempfile.TemporaryDirectory(prefix='camera-interface-upgrade-') as d:
  root=Path(d)/'rom';root.mkdir();work=Path(d)/'stage';work.mkdir()
  new=next(e for e in bundle['sources'] if e['path']==old['path'])
  path=root/old['path'];path.parent.mkdir(parents=True,exist_ok=True)
  path.write_bytes((ROOT/old['path']).read_bytes())
  assert runner.patch(root,new['patch'],reverse=True)[0], old['path']
  assert runner.patch(root,old['patch'])[0], old['path']
  # Outside patch hunks; the upgrade must preserve this edit.
  comment=b'\n# unrelated user change\n' if path.suffix!='.bp' else b'\n// unrelated user change\n'
  path.write_bytes(comment+path.read_bytes())
  small=dict(bundle);small['sources']=[new]
  changes=runner.source_stage(root,work,small,{},Path(d),argparse.Namespace())
  assert changes.get(old['path'],work/old['path']).read_bytes().startswith(comment)
print('PASS: explicit source modules, generated AIDL names, original SONAMEs, extraction mappings, idempotence, both predecessor upgrades and unrelated edits.')
