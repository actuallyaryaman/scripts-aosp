#!/usr/bin/env python3
"""Export a staging candidate as a standalone script; no source-tree mutation."""
import argparse,base64,difflib,gzip,hashlib,json,stat,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for option in ('root','donor','staging','output'):
 parser.add_argument('--'+option,required=True,type=Path)
args=parser.parse_args()
ROOT=args.root.resolve();DATA=Path(__file__).resolve().parent
work=args.staging.resolve();donor=args.donor.resolve()
hash=lambda b:hashlib.sha256(b).hexdigest()
source=[]
for name in json.loads((work/'files.json').read_text()):
 a=work/'before'/name;b=work/'after'/name
 before=a.read_bytes() if a.exists() else b'';after=b.read_bytes() if b.exists() else b''
 if before==after:continue
 diff=''.join(l if l.endswith('\n') else l+'\n\\ No newline at end of file\n' for l in difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile='a/'+name if a.exists() else '/dev/null',tofile='b/'+name if b.exists() else '/dev/null'))
 if not diff:continue
 e={'path':name,'patch':'diff --git a/'+name+' b/'+name+'\n'+('new file mode 100644\n' if not a.exists() else 'deleted file mode 100644\n' if not b.exists() else '')+diff,'before_sha256':hash(before) if a.exists() else None,'after_sha256':hash(after) if b.exists() else None,'mode':stat.S_IMODE(b.stat().st_mode) if b.exists() else 0o644}
 if name=='device/oneplus/aston/configs/camera-public.libraries.txt':e['merge_public_libraries']=after.decode().splitlines()
 if name.startswith('vendor/oneplus/camera/') and a.exists():e['package_base']=base64.b64encode(before).decode()
 source.append(e)
assets=[]
for e in json.loads((DATA/'camera-blobs.json').read_text())['files']:
 relative='proprietary/'+e['destination'];name='vendor/oneplus/aston/'+relative;p=donor/relative;old=ROOT/name
 data=p.read_bytes()
 assets.append({'path':name,'relative':relative,'origin':'donor','sha256':hash(data),'mode':stat.S_IMODE(p.stat().st_mode),'allowed_before':[hash(old.read_bytes())] if old.exists() else [],'url':'https://gitlab.com/alphadroid-project/vendor_oneplus_aston/-/raw/49904d23ca16083fbf101c5a50e1eb451d6b45d8/'+relative})
for name,h in json.loads((DATA/'baseline.json').read_text())['camera_package'].items():
 relative=name;name='vendor/oneplus/camera/'+relative;p=ROOT/name
 assets.append({'path':name,'relative':relative,'origin':'package','sha256':h,'mode':stat.S_IMODE(p.stat().st_mode),'allowed_before':[h],'url':'https://gitlab.com/alphadroid-project/vendor_oplus_camera/-/raw/d78f9c1fe4cfee562a298960c3bcabc86260aa6f/'+relative})
previous_path=DATA/'previous-bundle.json'
previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
if previous:assets=previous['assets']
private_path=work/'private-assets.json'
private=json.loads(private_path.read_text()) if private_path.exists() else []
asset_map={e['path']:e for e in assets}
for edit in private:
 prefix='vendor/oneplus/camera/' if edit.get('origin')=='package' else 'vendor/oneplus/aston/proprietary/'
 original=prefix+edit['original']
 target=prefix+edit['destination']
 base=dict(asset_map[original])
 base.update(path=target,input_sha256=edit['input_sha256'],sha256=edit['sha256'],rewrite_camera_elf=True)
 base['allowed_before']=list(set(base['allowed_before']+[edit['input_sha256']])) if target==original else []
 asset_map[target]=base
assets=list(asset_map.values())
bundle={'schema':1,'sources':source,'assets':assets,'upstream':json.loads((DATA/'upstream.json').read_text())}
bundle['elf_rewriter']=(DATA/'private_camera_elf.py').read_text()
bundle['legacy_sources']=previous.get('sources',[])
bundle['id']=hash(json.dumps(bundle,sort_keys=True).encode())[:20]
payload=base64.b64encode(gzip.compress(json.dumps(bundle,sort_keys=True).encode(),mtime=0)).decode()
runner=(DATA/'installer.py').read_text()
script='''#!/usr/bin/env bash
# Standalone aston camera port. Copy this file alone to rom-tools/ on another server.
set -euo pipefail
exec python3 - "$0" "$@" <<'CAMERA_PYTHON'
'''+runner+'''\nCAMERA_PYTHON
# CAMERA_PAYLOAD_BEGIN
'''+''.join('# '+payload[i:i+100]+'\n' for i in range(0,len(payload),100))+'# CAMERA_PAYLOAD_END\n'
p=args.output.resolve();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(script);p.chmod(0o755)
(p.parent/'resolved.patch').write_text(''.join(e['patch'] for e in source))
(p.parent/'bundle-summary.json').write_text(json.dumps({'id':bundle['id'],'source_files':len(source),'assets':len(assets),'donor_commit':'49904d23ca16083fbf101c5a50e1eb451d6b45d8','package_commit':'d78f9c1fe4cfee562a298960c3bcabc86260aa6f'},indent=2)+'\n')
print(f'{p}: {len(source)} source changes, {len(assets)} pinned assets, {len(script)} bytes')
