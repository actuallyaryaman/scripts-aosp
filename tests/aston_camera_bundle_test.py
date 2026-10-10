#!/usr/bin/env python3
"""Host installer integration tests on sparse temporary ROM copies. Never builds Android."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,tempfile
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--donor',required=True);args=ap.parse_args()
ROOT=Path(os.environ.get('ROM_ROOT', '.')).resolve();SCRIPT=TOOLS/'scripts/features/apply-aston-camera.sh'
spec=importlib.util.spec_from_file_location('camera_runner',TOOLS/'maintainer/camera-port/installer.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
bundle=runner.load_bundle(SCRIPT)
def run(root,*flags,ok=True):
 r=subprocess.run(['bash',str(SCRIPT),*flags,'--root',str(root),'--donor',args.donor,'--package',str(ROOT/'vendor/oneplus/camera')],capture_output=True,text=True)
 if (r.returncode==0)!=ok:raise AssertionError(r.stdout+r.stderr)
 return r.stdout+r.stderr
def snapshot(root):
 return {str(p.relative_to(root)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mode&0o777) for p in root.rglob('*') if p.is_file() and '.local-build' not in p.relative_to(root).parts and '.git' not in p.relative_to(root).parts}
def populate(root,clean=False):
 subprocess.run(['git','init','-q',str(root)],check=True)
 for e in bundle['sources']:
  src=ROOT/e['path'];dst=root/e['path']
  if e['before_sha256'] is None or not src.exists():continue
  dst.parent.mkdir(parents=True,exist_ok=True);data=src.read_bytes()
  if clean:
   relative=Path(e['path']);repo=src.parent
   while repo!=ROOT and not (repo/'.git').exists():repo=repo.parent
   if repo!=ROOT:
    r=subprocess.run(['git','-C',str(repo),'show','HEAD:'+str(src.relative_to(repo))],capture_output=True)
    if r.returncode==0:data=r.stdout
  dst.write_bytes(data);dst.chmod(src.stat().st_mode&0o777)
  # Reconstruct the original source when the live checkout already has this bundle.
  if runner.patch(root,e['patch'],reverse=True,check=True)[0]:
   assert runner.patch(root,e['patch'],reverse=True)[0]
  # Exercise actual transactions with independent edits at both file boundaries,
  # not only source staging. Keep fixture comment syntax appropriate to each file.
  data=dst.read_bytes();suffix=dst.suffix
  marker=b'//' if suffix in ('.bp','.java','.cpp','.h','.cc') else b';;' if suffix=='.cil' else b'#'
  prefix=marker+b' unrelated boundary prefix\n';tail=b'\n'+marker+b' unrelated boundary suffix\n'
  if suffix=='.xml':
   prefix=b'<!-- unrelated boundary prefix -->\n';tail=b'\n<!-- unrelated boundary suffix -->\n'
   if data.startswith(b'<?xml'):
    declaration,rest=data.split(b'\n',1);data=declaration+b'\n'+prefix+rest;prefix=b''
  dst.write_bytes(prefix+data+tail)
 for e in bundle['assets']:
  p=ROOT/e['path'];dst=root/e['path']
  if not p.is_file() or dst.exists():continue
  if e.get('rewrite_camera_elf'):
   original=ROOT/('vendor/oneplus/camera/' if e['origin']=='package' else 'vendor/oneplus/aston/')/e['relative']
   if original!=p:continue  # private renamed aliases must be created by apply
   data=original.read_bytes()
   if hashlib.sha256(data).hexdigest()!=e['input_sha256']:
    data=(ROOT/'.local-build/aston-camera/backups'/e['input_sha256']).read_bytes()
   dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data);dst.chmod(e['mode']);continue
  dst.parent.mkdir(parents=True,exist_ok=True);os.link(p,dst)
 for name in ('frameworks/base/Android.bp','build/make/core/main.mk'):
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists():p.write_text('// fixture root marker\n')
 public=root/'vendor/oneplus/sm8550-common/proprietary/vendor/etc/public.libraries.txt'
 public.parent.mkdir(parents=True,exist_ok=True);public.write_text('libunrelated_custom.so\n')
 (root/'unrelated-user-mod.txt').write_text('must survive all camera operations\n')
 allow=root/'build/soong/scripts/check_boot_jars/package_allowed_list.txt'
 allow.write_text('# Unrelated local bootclasspath entry\ncom\\.example\\.local\n\n'+allow.read_text())
 subprocess.run(['git','init','-q',str(root)],check=True)
 subprocess.run(['git','-C',str(root),'add','unrelated-user-mod.txt'],check=True)
with tempfile.TemporaryDirectory(prefix='camera-installer-test-',dir=ROOT/'.local-build') as d:
 root=Path(d)/'rom';root.mkdir();populate(root)
 before=snapshot(root);index=(root/'.git/index').read_bytes()
 print(run(root,'--check'),end='');assert before==snapshot(root)
 print(run(root,'--apply'),end='');after=snapshot(root);assert before!=after
 assert index==(root/'.git/index').read_bytes()
 assert 'libunrelated_custom.so' in (root/'device/oneplus/aston/configs/camera-public.libraries.txt').read_text()
 assert (root/'unrelated-user-mod.txt').read_text()=='must survive all camera operations\n'
 allow=root/'build/soong/scripts/check_boot_jars/package_allowed_list.txt'
 assert 'com\\.example\\.local' in allow.read_text()
 assert 'com\\.color\\.inner\\.content\\.res' in allow.read_text()
 assert 'com\\.color\\.inner\\.view' in allow.read_text()
 assert 'already applied' in run(root,'--apply');assert after==snapshot(root)
 # Later overlapping edits are refused by reverse, before any reversal writes.
 path=root/'device/oneplus/aston/device.mk';original=path.read_bytes();path.write_bytes(original+b'\n# later edit\n')
 conflict=snapshot(root);assert 'later edit' in run(root,'--reverse',ok=False);assert conflict==snapshot(root);path.write_bytes(original)
 print(run(root,'--reverse'),end='');assert before==snapshot(root)
 # Simulate repo sync by undoing source changes while leaving installed vendor assets.
 run(root,'--apply')
 for e in bundle['sources']:
  p=root/e['path'];record=next((v for v in json.loads((root/'.local-build/aston-camera/journal.json').read_text())['files'] if v['path']==e['path']),None)
  if record and record['before'] is not None:
   p.write_bytes((root/'.local-build/aston-camera/backups'/record['before']).read_bytes());p.chmod(record['mode_before'])
  elif record and p.exists():p.unlink()
 print(run(root,'--apply'),end='');assert after==snapshot(root)
 # Interrupted transaction recovery restores the last pre-apply source state.
 jp=root/'.local-build/aston-camera/journal.json';j=json.loads(jp.read_text());j['state']='applying';jp.write_text(json.dumps(j))
 print(run(root,'--recover'),end='')
 # Real source overlap must cause a completely read-only failure.
 target=root/'device/oneplus/aston/device.mk';target.write_text('conflicting replacement\n');conflict=snapshot(root)
 assert 'Source conflicts' in run(root,'--apply',ok=False);assert conflict==snapshot(root)
 # Check on clean Git HEAD files, without Separate App Sound/font mods, and copied script alone.
 clean=Path(d)/'ROM with spaces';clean.mkdir();populate(clean,clean=True);before=snapshot(clean)
 portable=Path(d)/'standalone camera.sh';shutil.copy2(SCRIPT,portable);saved=SCRIPT;SCRIPT=portable
 print(run(clean,'--check'),end='');assert before==snapshot(clean)
 # Relative script/root paths work from a different working directory. Inherited
 # Git environment must not redirect patch operations to another repository.
 environment=dict(os.environ,GIT_DIR=str(Path(d)/'invalid-git-dir'),GIT_WORK_TREE=str(ROOT))
 relative=subprocess.run(['bash',portable.name,'--check','--root',clean.name,'--donor',args.donor,'--package',str(ROOT/'vendor/oneplus/camera')],cwd=d,env=environment,capture_output=True,text=True)
 assert relative.returncode==0,relative.stdout+relative.stderr
 assert before==snapshot(clean)
 # Missing entire app package works from embedded text plus the pinned offline package source.
 shutil.rmtree(clean/'vendor/oneplus/camera');run(clean,'--apply')
 assert (clean/'vendor/oneplus/camera/proprietary/product/priv-app/OplusCamera/OplusCamera.apk').exists()
 print('PASS: standalone copy, no other mods, missing package, dry run, apply, repeat, sync, reverse, recovery, conflicts, Git index preservation.')
