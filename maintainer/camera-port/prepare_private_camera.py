"""Executed in the staging generator after source-module names are disambiguated."""
exec((DATA/'private_camera_elf.py').read_text())
manifest=json.loads((DATA/'camera-blobs.json').read_text())['files']
private_files={};renamed={};transform_assets=[]
for e in manifest:
 d=e['destination'];data=(DONOR/'proprietary'/d).read_bytes()
 if data[:4]!=b'\x7fELF':continue
 result=rewrite_camera_elf(data)
 if result==data:continue
 leaf=Path(d).name;target=str(Path(d).with_name(PRIVATE_CAMERA_NAMES.get(leaf,leaf)))
 renamed[d]=target
 private_files[target]=(data,result)
 transform_assets.append({'original':d,'destination':target,'input_sha256':hashlib.sha256(data).hexdigest(),'sha256':hashlib.sha256(result).hexdigest(),'input_sha1':hashlib.sha1(data).hexdigest(),'output_sha1':hashlib.sha1(result).hexdigest()})
# Only named camera stock modules get private filenames. All their ELF consumers are pinned assets.
p='vendor/oneplus/aston/Android.bp';s=read(p)
for old,new in PRIVATE_CAMERA_NAMES.items():
 s=s.replace('"proprietary/vendor/lib64/'+old+'"','"proprietary/vendor/lib64/'+new+'"')
 s=s.replace('"proprietary/odm/lib64/'+old+'"','"proprietary/odm/lib64/'+new+'"')
 s=s.replace('stem: "'+old[:-3]+'"','stem: "'+new[:-3]+'"')
put(p,s)
# Source->destination rename keeps original OTA/donor filenames, while extraction installs private names.
p='device/oneplus/aston/proprietary-files.txt';lines=read(p).splitlines();pins={e['original']:e for e in transform_assets}
for i,line in enumerate(lines):
 if not line or line.startswith('#'):continue
 prefix=line.split('|',1)[0];key=prefix.split(';')[0].split(':')[-1].lstrip('-')
 if key not in pins:continue
 e=pins[key];tail=';'+prefix.split(';',1)[1] if ';' in prefix else ''
 spec=prefix.split(';')[0]
 if key!=e['original']:spec=e['original']+':'+key
 elif e['destination']!=key:
  spec=spec.split(':')[0]+':'+e['destination']
  # Explicit module names are required: lib_fixups only maps dependencies.
  name=Path(key).name[:-3]+'_'+key.split('/')[0]
  tail=';MODULE='+name
 lines[i]=spec+tail+'|'+line.split('|')[1]+'|'+e['output_sha1']
# Preserve explicit names for the other disambiguated, unrenamed interface files too.
for i,line in enumerate(lines):
 if not line or line.startswith('#'):continue
 prefix=line.split('|',1)[0];dest=prefix.split(';')[0].split(':')[-1].lstrip('-')
 leaf=Path(dest).name
 if leaf in ('vendor.oplus.hardware.camera_rfi-V1-ndk.so','vendor.oplus.hardware.cameraextension-V1-ndk.so'):
  lines[i]=prefix.split(';')[0]+';MODULE='+leaf[:-3]+'_'+dest.split('/')[0]+'|'+'|'.join(line.split('|')[1:])
put(p,'\n'.join(lines)+'\n')
# Extraction must reproduce the same byte edits and map private SONAMEs to distinct Soong names.
put('device/oneplus/aston/camera_private_libs.py',(DATA/'private_camera_elf.py').read_text())
p='device/oneplus/aston/extract-files.py';s=read(p)
s=s.replace('from extract_utils.fixups_blob import (','from camera_private_libs import camera_private_blob_fixup\n\nfrom extract_utils.fixups_blob import (',1)
s=s.replace("    # These stock interfaces must not replace",'''    # Private filenames map back to the disambiguated build modules.
    private_names = {
        'vendor.oplus.hardware.cammidasservice-C1-ndk': 'vendor.oplus.hardware.cammidasservice-V1-ndk',
        'vendor.oplus.hardware.commondcs-C1-ndk_platform': 'vendor.oplus.hardware.commondcs-V1-ndk_platform',
        'vendor.oplus.hardware.sendextcamcmd-C2-ndk': 'vendor.oplus.hardware.sendextcamcmd-V2-ndk',
    }
    lib = private_names.get(lib, lib)
    # These stock interfaces must not replace''',1)
marker='    ): lib_fixup_camera_partition,'
s=s.replace(marker,"        'vendor.oplus.hardware.cammidasservice-C1-ndk',\n        'vendor.oplus.hardware.commondcs-C1-ndk_platform',\n        'vendor.oplus.hardware.sendextcamcmd-C2-ndk',\n"+marker,1)
paths=sorted(private_files)
addition='''# Apply existing fixups first, then same-length SONAME/NEEDED edits; never regenerate live.
_CAMERA_PRIVATE_FILES = '''+repr(paths)+'''
for _camera_path in _CAMERA_PRIVATE_FILES:
    _camera_fixup = next((value for key, value in blob_fixups.items()
            if _camera_path == key or isinstance(key, tuple) and _camera_path in key), None)
    if _camera_fixup is None:
        _camera_fixup = blob_fixup()
        blob_fixups[_camera_path] = _camera_fixup
    _camera_fixup.call(camera_private_blob_fixup)

'''
s=s.replace('module = ExtractUtilsModule(',addition+'module = ExtractUtilsModule(',1);put(p,s)
# libcsextimpl uses the stock system sendextcmd copy; isolate this pair as well.
p='vendor/oneplus/camera/Android.bp';s=read(p)
s=s.replace('stem: "vendor.oplus.hardware.sendextcamcmd-V2-ndk"','stem: "vendor.oplus.hardware.sendextcamcmd-C2-ndk"')
put(p,s)
for file in (ROOT/'vendor/oneplus/camera/proprietary').rglob('*'):
 if not file.is_file():continue
 data=file.read_bytes()
 if data[:6]!=b'\x7fELF\x02\x01':continue
 result=rewrite_camera_elf(data)
 if result==data:continue
 relative=str(file.relative_to(ROOT/'vendor/oneplus/camera'))
 transform_assets.append({'origin':'package','original':relative,'destination':relative,'input_sha256':hashlib.sha256(data).hexdigest(),'sha256':hashlib.sha256(result).hexdigest()})
(WORK/'private-assets.json').write_text(json.dumps(transform_assets,indent=2))
print('Private camera ELF files:',len(transform_assets))
