# SPDX-License-Identifier: Apache-2.0
# Host-side bundle tests. Never builds Android or alters the source checkout.
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
import base64,gzip,hashlib,json,os,re,shutil,subprocess,tempfile,sys
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(os.environ.get('ROM_ROOT', '.')).resolve()
SCRIPT=TOOLS/'scripts/features/apply-separate-app-sound.sh'
encoded=re.search(r"PAYLOAD = '''\n(.*?)'''",SCRIPT.read_text(),re.S).group(1)
P=json.loads(gzip.decompress(base64.b64decode(encoded)))
base=Path(tempfile.mkdtemp(prefix='sas-fixture-',dir='/tmp'))
root=base/'rom';root.mkdir();(root/'.repo').mkdir()
def git(project,*args):return subprocess.check_output(['git','-C',str(root/project),*args],stderr=subprocess.STDOUT)
for project in P['patches']:
 d=root/project;d.mkdir(parents=True)
 git(project,'init','-q');git(project,'config','user.name','Fixture');git(project,'config','user.email','fixture@example.invalid')
 for f in P['files']:
  if f['project']==project and f['before'] is not None:
   target=root/f['path'];target.parent.mkdir(parents=True,exist_ok=True);original=subprocess.check_output(['git','-C',str(R/project),'show','HEAD:'+f['relative']])
   target.write_bytes(original);target.chmod(f['mode'])
 (d/'unrelated.txt').write_text('original\n')
 git(project,'add','.');git(project,'-c','commit.gpgsign=false','commit','-qm','baseline')
 (d/'unrelated.txt').write_text('user edit\n')
def state():
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for project in P['patches'] for p in (root/project).rglob('*') if p.is_file() and '.git' not in p.parts}
def indexes():return {p:hashlib.sha256((root/p/'.git/index').read_bytes()).hexdigest() for p in P['patches']}
def run(op,success=True,env=None,umask=-1):
 r=subprocess.run(['bash',str(SCRIPT),op,str(root)],capture_output=True,text=True,env=env,umask=umask)
 assert (r.returncode==0)==success,(op,r.returncode,r.stdout,r.stderr)
 print(op,':',r.stdout.strip().replace('\n',' | '),r.stderr.strip())
 return r
initial=state();idx=indexes()
run('--check');assert state()==initial and indexes()==idx
run('--apply');applied=state();assert indexes()==idx
run('--apply');assert state()==applied and indexes()==idx
run('--check');run('--status')
run('--reverse');assert state()==initial and indexes()==idx
run('--reverse');assert state()==initial
# A touched-file edit must stop before any other project changes.
f=next(f for f in P['files'] if f['before'] is not None);target=root/f['path'];saved=target.read_bytes();target.write_bytes(saved+b'// user edit\n')
dirty=state();run('--apply',False);assert state()==dirty and indexes()==idx
target.write_bytes(saved)
# A staged edit is rejected even when the working tree matches the original hash.
target.write_bytes(saved+b'// staged edit\n');git(f['project'],'add',f['relative']);target.write_bytes(saved)
run('--check',False);git(f['project'],'reset','-q','HEAD','--',f['relative']);assert state()==initial;idx=indexes()
# A failed second-project apply restores first-project changes and leaves user edits intact.
realgit=shutil.which('git');binpath=base/'bin';binpath.mkdir()
shim=binpath/'git';shim.write_text('#!/usr/bin/env python3\nimport os,sys\nargs=sys.argv[1:]\nif "apply" in args and "--check" not in args and '+repr(str(root/'frameworks/av'))+' in args:\n print("injected apply failure",file=sys.stderr);sys.exit(42)\nos.execv('+repr(realgit)+','+'['+repr(realgit)+']+args)\n');shim.chmod(0o755)
env=os.environ.copy();env['PATH']=str(binpath)+':'+env['PATH']
run('--apply',False,env);assert state()==initial and indexes()==idx
run('--apply');assert state()==applied
# Reversal must preserve a later user modification.
target.write_bytes(target.read_bytes()+b'// later edit\n');later=state();run('--reverse',False);assert state()==later
# Restore the fixture's applied file without relying on the source checkout's state.
target.write_bytes(saved)
subprocess.run(['git','-C',str(root/f['project']),'apply','--include='+f['relative']],input=P['patches'][f['project']].encode(),check=True)
run('--reverse');assert state()==initial
# A different baseline permission is accepted and preserved through reversal.
target.chmod(0o600);permission_state=state();run('--apply');assert target.stat().st_mode & 0o777==0o600
run('--reverse');assert state()==permission_state and target.stat().st_mode & 0o777==0o600
target.chmod(f['mode'])
# An interrupted transaction is recovered before a new application.
run('--apply');journalpath=root/'.local-build/separate-app-sound/transaction.json'
journal=json.loads(journalpath.read_text());journal['status']='applying';journalpath.write_text(json.dumps(journal))
run('--apply');assert state()==applied and indexes()==idx
run('--reverse');assert state()==initial
# Another clean revision and group-writable files must not need the embedded baseline hashes.
portable=next(item for item in P['files'] if item['path'].endswith('/include/media/AudioPolicy.h'))
portable_target=root/portable['path'];portable_saved=portable_target.read_bytes()
portable_target.write_bytes(b'// Fixture: another clean upstream revision.\n'+portable_saved)
git(portable['project'],'add',portable['relative'])
git(portable['project'],'-c','commit.gpgsign=false','commit','-qm','Different upstream revision')
for item in P['files']:
 path=root/item['path']
 if path.exists():path.chmod(0o664)
initial=state();idx=indexes()
run('--check');assert state()==initial and indexes()==idx
run('--apply',False,env,umask=0o002);assert state()==initial and indexes()==idx
run('--apply',umask=0o002);applied=state();assert indexes()==idx and portable_target.stat().st_mode & 0o777==0o664
assert all((root/item['path']).stat().st_mode & 0o777==0o664 for item in P['files'])
run('--check');run('--apply');assert state()==applied
# A later permission change is still protected by the installation's own manifest.
portable_target.chmod(0o600);run('--reverse',False);assert state()==applied
portable_target.chmod(0o664)
portable_target.write_bytes(portable_target.read_bytes()+b'// Later edit on portable install.\n')
later=state();run('--reverse',False);assert state()==later
portable_target.write_bytes(portable_target.read_bytes().removesuffix(b'// Later edit on portable install.\n'))
journal=json.loads(journalpath.read_text());journal['status']='applying';journalpath.write_text(json.dumps(journal))
run('--apply');assert state()==applied and indexes()==idx
run('--reverse');assert state()==initial and indexes()==idx and portable_target.stat().st_mode & 0o777==0o664
# An actual upstream conflict is reported without any source writes.
portable_target.write_bytes(b'// Incompatible fixture.\n')
git(portable['project'],'add',portable['relative'])
git(portable['project'],'-c','commit.gpgsign=false','commit','-qm','Incompatible upstream revision')
conflicted=state();run('--apply',False);assert state()==conflicted
portable_target.write_bytes(b'// Fixture: another clean upstream revision.\n'+portable_saved)
git(portable['project'],'add',portable['relative'])
git(portable['project'],'-c','commit.gpgsign=false','commit','-qm','Restore compatible revision')
initial=state()
# A manually partial bundle is reported and refused without trying to fill in missing files.
project=next(iter(P['patches']));subprocess.run(['git','-C',str(root/project),'apply'],input=P['patches'][project].encode(),check=True)
partial=state();run('--status',False);run('--apply',False);assert state()==partial
print('PASS: portable revisions and permissions, conflicts, transactions and interrupted recovery; unrelated edits and indexes preserved.')
shutil.rmtree(base)
