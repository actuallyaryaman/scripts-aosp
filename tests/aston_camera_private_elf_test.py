#!/usr/bin/env python3
"""Verify private ELF names, unchanged code bytes, dependency closure and install uniqueness."""
import importlib.util,re,struct,collections,json,sys
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('ROM_ROOT', '.')).resolve()
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
runner=load('runner',TOOLS/'maintainer/camera-port/installer.py');bundle=runner.load_bundle(TOOLS/'scripts/features/apply-aston-camera.sh')
elf=load('elf',TOOLS/'maintainer/camera-port/private_camera_elf.py')
assets={e['path']:e for e in bundle['assets']}
changed=[]
for e in bundle['assets']:
 if not e.get('rewrite_camera_elf'):continue
 before=ROOT/('vendor/oneplus/camera/' if e['origin']=='package' else 'vendor/oneplus/aston/')/e['relative']
 # Originals are preserved under their old filenames for renamed blobs; overwritten consumers
 # can be read from the recorded transaction backup after applying.
 data=before.read_bytes()
 if runner.digest(data)!=e['input_sha256']:
  saved=ROOT/'.local-build/aston-camera/backups'/e['input_sha256']
  data=saved.read_bytes()
 assert runner.digest(data)==e['input_sha256']
 result=elf.rewrite_camera_elf(data);assert runner.digest(result)==e['sha256']
 assert len(data)==len(result) and elf.rewrite_camera_elf(result)==result
 entries=elf.elf_dynamic_strings(data)
 allowed={p+i for tag,p,value in entries if value in elf.PRIVATE_CAMERA_NAMES for i in range(len(value))}
 assert all(i in allowed for i,(a,b) in enumerate(zip(data,result)) if a!=b),e['path']
 phoff=struct.unpack_from('<Q',data,32)[0];ents,count=struct.unpack_from('<HH',data,54)
 for i in range(count):
  typ,flags,off,addr,phys,size,mem,align=struct.unpack_from('<IIQQQQQQ',data,phoff+i*ents)
  if typ==1 and flags&1:assert data[off:off+size]==result[off:off+size],e['path']
 assert not any(value in elf.PRIVATE_CAMERA_NAMES for tag,p,value in elf.elf_dynamic_strings(result))
 assert runner.digest((ROOT/e['path']).read_bytes())==e['sha256'],e['path']
 changed.append(e['path'])
# Project the last generated install rules onto corrected prebuilt stems. Never edits output.
installs=ROOT/'.local-build/out/soong/installs-voltage_aston.mk';rules=collections.defaultdict(set)
for line in installs.read_text().splitlines():
 if not line.startswith('out/target/product/aston/') or ': ' not in line:continue
 dest,source=line.split(': ',1);source=source.split(' | ')[0]
 if 'out/soong/.intermediates/' not in source:continue
 if '/vendor/oneplus/aston/' in source or '/vendor/oneplus/camera/' in source:
  leaf=Path(dest).name
  if leaf in elf.PRIVATE_CAMERA_NAMES:dest=str(Path(dest).with_name(elf.PRIVATE_CAMERA_NAMES[leaf]))
 rules[dest].add(source)
collisions={d:sorted(s) for d,s in rules.items() if len(s)>1}
assert not collisions,collisions
# Every existing native ELF definition must describe the desired SONAME dependency names.
for path in ['vendor/oneplus/aston/Android.bp','vendor/oneplus/camera/Android.bp']:
 text=(ROOT/path).read_text()
 for old,new in elf.PRIVATE_CAMERA_NAMES.items():
  assert 'stem: "'+old[:-3]+'"' not in text,(path,old)
print(f'PASS: {len(changed)} transformed ELFs; hashes, same-length strings, executable bytes, repeatability and zero projected duplicate install paths.')
