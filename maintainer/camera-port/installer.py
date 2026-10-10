"""Embedded standalone runner. No imports from other ROM tool scripts."""
import argparse,base64,concurrent.futures,fcntl,gzip,hashlib,json,os,shutil,signal,stat,subprocess,sys,tempfile
from pathlib import Path

def sha(path):
 if not path.exists():return None
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def safe(root,name):
 p=Path(name)
 if p.is_absolute() or '..' in p.parts:raise RuntimeError('Unsafe path: '+name)
 p=root/p
 if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):raise RuntimeError('Symlink or escaped path: '+name)
 if p.exists() and not p.is_file():raise RuntimeError('Expected a regular file: '+name)
 return p
def atomic(path,data,mode=0o644):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,name=tempfile.mkstemp(prefix='.aston-camera-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(name,mode);os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
def writejson(path,value):atomic(path,json.dumps(value,indent=2).encode())
def load_bundle(script):
 s=script.read_text();payload=s.split('# CAMERA_PAYLOAD_BEGIN\n',1)[1].split('# CAMERA_PAYLOAD_END',1)[0]
 bundle=json.loads(gzip.decompress(base64.b64decode(''.join(l[2:] for l in payload.splitlines()))))
 if bundle.get('elf_rewriter'):exec(bundle['elf_rewriter'],globals())
 return bundle
def patch(work,text,reverse=False,check=False):
 # Allow offsets at file boundaries while still checking every supplied hunk
 # context/removal line. No --reject, --3way, or whitespace-ignoring fallback.
 args=['git','-C',str(work),'apply','--no-index','--whitespace=nowarn','--unidiff-zero']
 if reverse:args+=['--reverse']
 if check:args+=['--check']
 r=subprocess.run(args+['-'],input=text,text=True,capture_output=True,env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')})
 return r.returncode==0,r.stderr.strip()
def source_stage(root,work,bundle,asset_map,cache,args):
 subprocess.run(['git','init','-q',str(work)],check=True,env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')})
 changes={};conflicts=[]
 for e in bundle['sources']:
  name=e['path'];live=safe(root,name);p=work/name;p.parent.mkdir(parents=True,exist_ok=True)
  before=live.read_bytes() if live.exists() else None
  if before is not None:p.write_bytes(before)
  elif e.get('package_base'):
   p.write_bytes(base64.b64decode(e['package_base']))
  if e.get('merge_public_libraries'):
   lines=before.decode().splitlines() if before is not None else []
   common=safe(root,'vendor/oneplus/sm8550-common/proprietary/vendor/etc/public.libraries.txt')
   additional=(common.read_text().splitlines() if common.exists() else [])+e['merge_public_libraries']
   for line in additional:
    if line not in lines:lines.append(line)
   result=('\n'.join(lines)+'\n').encode();p.write_bytes(result)
   if result!=before:changes[name]=p
   continue
  if before is not None and digest(before)==e['after_sha256']:continue
  # Prefer recognition of a fully applied patch before trying insertion hunks:
  # unrelated boundary edits must not cause append-only hunks to be duplicated.
  if p.exists() and patch(work,e['patch'],reverse=True,check=True)[0]:continue
  ok,msg=patch(work,e['patch'],check=True)
  if ok:
   ok,msg=patch(work,e['patch'])
   if not ok:raise RuntimeError(msg)
  else:
   candidates=[v for v in bundle.get('legacy_sources',[]) if v['path']==name]
   candidates.sort(key=lambda v:v['after_sha256']!=digest(before or b''))
   staged=p.read_bytes() if p.exists() else None
   upgraded=False
   for legacy in candidates:
    if staged is not None:p.write_bytes(staged)
    if not patch(work,legacy['patch'],reverse=True,check=True)[0]:continue
    ok,msg=patch(work,legacy['patch'],reverse=True)
    if ok:ok,msg=patch(work,e['patch'],check=True)
    if ok:ok,msg=patch(work,e['patch'])
    if ok:upgraded=True;break
   if not upgraded:conflicts.append(name+'\n'+msg);continue
  result=p.read_bytes() if p.exists() else None
  if result!=before:changes[name]=p if result is not None else None
 if conflicts:raise RuntimeError('Source conflicts; ROM source was not changed:\n\n'+'\n\n'.join(conflicts))
 return changes

def get_asset(e,root,cache,args,download=False):
 name=e['path'];want=e['sha256'];p=safe(root,name)
 if p.exists() and sha(p)==want:return p
 # Refuse unknown changes to bundled app assets; camera vendor transitions are explicit pins.
 if p.exists() and sha(p) not in e.get('allowed_before',[])+[e.get('input_sha256')]:
  raise RuntimeError('Unrecognized local asset edit: '+name+'; preserve or resolve it before applying')
 cached=cache/'downloads'/want
 if cached.is_file() and sha(cached)==want:return cached
 candidates=[]
 if e.get('rewrite_camera_elf'):
  candidates.extend([p,safe(root,('vendor/oneplus/camera/' if e['origin']=='package' else 'vendor/oneplus/aston/')+e['relative']),cache/'downloads'/e['input_sha256']])
 if args.donor and e['origin']=='donor':candidates.append(Path(args.donor)/e['relative'])
 if args.package and e['origin']=='package':candidates.append(Path(args.package)/e['relative'])
 for candidate in candidates:
  if candidate.is_file() and sha(candidate)==want:return candidate
  if e.get('rewrite_camera_elf') and candidate.is_file() and sha(candidate)==e['input_sha256']:
   result=rewrite_camera_elf(candidate.read_bytes())
   if digest(result)!=want:raise RuntimeError('Unexpected ELF rewrite result: '+name)
   atomic(cached,result,e['mode']);return cached
 if not download:return None
 cached.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='download-',dir=cached.parent);os.close(fd)
 try:
  r=subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','3','--connect-timeout','20','--max-time','600','--output',tmp,e['url']],capture_output=True,text=True)
  if r.returncode:raise RuntimeError('Download failed: '+name+'\n'+r.stderr.strip())
  if e.get('rewrite_camera_elf'):
   if sha(Path(tmp))!=e['input_sha256']:raise RuntimeError('Input checksum mismatch: '+name)
   result=rewrite_camera_elf(Path(tmp).read_bytes())
   Path(tmp).write_bytes(result)
  if sha(Path(tmp))!=want:raise RuntimeError('Checksum mismatch (or Git LFS pointer) for '+name)
  os.chmod(tmp,e['mode']);os.replace(tmp,cached)
  return cached
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def state(root,journal):
 counts={'before':0,'after':0,'edited':0}
 for e in journal['files']:
  h=sha(safe(root,e['path']))
  counts['after' if h==e['after'] else 'before' if h==e['before'] else 'edited']+=1
 return counts

def restore(root,cache,journal,strict=True):
 # Check every path and backup before making the first reversal write.
 for e in journal['files']:
  p=safe(root,e['path']);h=sha(p)
  if h not in (e['before'],e['after']):raise RuntimeError('Rollback blocked by later edit: '+e['path'])
  if e['before'] is not None and sha(cache/'backups'/e['before'])!=e['before']:
   raise RuntimeError('Missing/corrupt rollback backup: '+e['path'])
 for e in reversed(journal['files']):
  p=safe(root,e['path'])
  if sha(p)==e['before']:continue
  if e['before'] is None:
   p.unlink(missing_ok=True)
  else:atomic(p,(cache/'backups'/e['before']).read_bytes(),e['mode_before'])
 journal['state']='reversed';writejson(cache/'journal.json',journal)

def transact(root,cache,changes,modes,bundle):
 files=[]
 for name,target in sorted(changes.items()):
  p=safe(root,name);old=sha(p);new=sha(target) if target is not None else None
  mode=stat.S_IMODE(p.stat().st_mode) if p.exists() else None
  if old==new:continue
  if old is not None:
   backup=cache/'backups'/old
   if sha(backup)!=old:atomic(backup,p.read_bytes(),mode)
  files.append({'path':name,'before':old,'after':new,'mode_before':mode,'mode_after':modes.get(name,mode or 0o644)})
 journal={'state':'applying','bundle_id':bundle['id'],'files':files}
 previous=cache/'journal.json'
 if previous.exists():
  old=previous.read_bytes();atomic(cache/'history'/(digest(old)+'.json'),old)
 writejson(previous,journal)
 try:
  for e in files:
   p=safe(root,e['path'])
   if sha(p)!=e['before']:raise RuntimeError('File changed during apply: '+e['path'])
   if e['after'] is None:p.unlink(missing_ok=True)
   else:
    source=changes[e['path']]
    if sha(source)!=e['after']:raise RuntimeError('Staged asset changed: '+e['path'])
    atomic(p,source.read_bytes(),e['mode_after'])
  journal['state']='applied';writejson(previous,journal)
 except BaseException:
  print('Apply interrupted; restoring transaction backups.',file=sys.stderr)
  restore(root,cache,journal);raise
 return len(files)

def main():
 ap=argparse.ArgumentParser(description='Standalone aston-only OnePlus Camera, Gallery and editor port. Does not build, sync, commit or flash.')
 group=ap.add_mutually_exclusive_group(required=True)
 for mode in ('check','apply','status','reverse','recover','show-patch'):group.add_argument('--'+mode,action='store_true')
 ap.add_argument('--root',default='.',help='ROM source root (default: current directory)')
 ap.add_argument('--donor',help='Optional offline pinned vendor_oneplus_aston checkout')
 ap.add_argument('--package',help='Optional offline pinned vendor_oplus_camera checkout')
 args=ap.parse_args(sys.argv[2:]);bundle=load_bundle(Path(sys.argv[1]));root=Path(args.root).resolve()
 for required in ('device/oneplus/aston/device.mk','device/oneplus/aston/BoardConfig.mk','frameworks/base/Android.bp','build/make/core/main.mk'):
  if not (root/required).is_file():raise RuntimeError('Not a supported aston ROM checkout: missing '+required)
 if args.show_patch:
  for e in bundle['sources']:print(e['patch'],end='')
  return
 for cmd in ('git','curl'):
  if not shutil.which(cmd):raise RuntimeError('Required host command missing: '+cmd)
 cache=root/'.local-build/aston-camera'
 if cache.is_symlink() or not cache.resolve().is_relative_to(root):raise RuntimeError('Unsafe cache directory')
 cache.mkdir(parents=True,exist_ok=True)
 # Parent cache paths may not escape through pre-existing symlinks.
 for sub in ('downloads','backups','history'):
  p=cache/sub
  if p.is_symlink():raise RuntimeError('Unsafe cache subdirectory: '+str(p))
 lock=cache/'lock'
 if lock.is_symlink():raise RuntimeError('Unsafe lock file')
 with lock.open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('Another camera installer is running for this ROM')
  jp=cache/'journal.json'
  if jp.is_symlink():raise RuntimeError('Unsafe journal file')
  journal=json.loads(jp.read_text()) if jp.exists() else None
  if args.status:
   print('Bundle: '+bundle['id'])
   print('No apply transaction recorded.' if not journal else json.dumps({'transaction':journal['state'],'files':state(root,journal)},indent=2));return
  if args.reverse or args.recover:
   if not journal:raise RuntimeError('No transaction backup exists on this server')
   if args.recover and journal['state']!='applying':print('No interrupted transaction to recover.');return
   restore(root,cache,journal);print('Restored the files changed by the latest apply transaction.');return
  if journal and journal['state']=='applying':raise RuntimeError('Interrupted transaction found. Run --recover first.')
  with tempfile.TemporaryDirectory(prefix='camera-stage-',dir=cache) as temp:
   work=Path(temp);assets={e['path']:e for e in bundle['assets']}
   changes=source_stage(root,work,bundle,assets,cache,args)
   sources={e['path'] for e in bundle['sources']};missing=[];modes={e['path']:stat.S_IMODE(safe(root,e['path']).stat().st_mode) if safe(root,e['path']).exists() else e['mode'] for e in bundle['sources']}
   def qualify(e):return e,get_asset(e,root,cache,args,download=args.apply)
   remaining=[e for e in bundle['assets'] if e['path'] not in sources]
   print(f'Source checks passed; checking {len(remaining)} pinned assets.',flush=True)
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for e,p in pool.map(qualify,remaining):
     if p is None:missing.append(e['path'])
     elif sha(safe(root,e['path']))!=e['sha256']:changes[e['path']]=p;modes[e['path']]=e['mode']
   # Patch source files from an existing/embedded package baseline; all base bytes are embedded.
   if args.check:
    print(f'Dry run: {len(changes)} files would change; {len(missing)} assets need download (no network requested).')
    if missing:print('Use --apply to download the pinned assets, or --donor/--package for offline input.')
    print('ROM source was not changed.');return
   if not changes:print('Camera port is already applied; nothing to change.');return
   n=transact(root,cache,changes,modes,bundle)
   print(f'Applied {n} files. Backup: .local-build/aston-camera/journal.json')
   print('Build and flash using your usual commands. Device validation is still required.')

if __name__=='__main__':
 def interrupted(signum,frame):raise KeyboardInterrupt('signal '+str(signum))
 signal.signal(signal.SIGTERM,interrupted)
 try:main()
 except (RuntimeError,OSError,ValueError,KeyboardInterrupt) as e:
  print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
