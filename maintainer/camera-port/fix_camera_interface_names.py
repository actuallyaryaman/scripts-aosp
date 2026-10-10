"""Keep stock camera AIDL prebuilts distinct from source-built system_ext interfaces."""
import re
RENAMES={
 'vendor.oplus.hardware.commondcs-V1-ndk_platform':'vendor',
 'vendor.oplus.hardware.camera_rfi-V1-ndk':'odm',
 'vendor.oplus.hardware.cameraextension-V1-ndk':'vendor',
 'vendor.oplus.hardware.cammidasservice-V1-ndk':None,
 'vendor.oplus.hardware.sendextcamcmd-V2-ndk':'odm',
}
def fix_bp(text):
 # Blueprint braces inside strings/comments are ignored.
 tokens=re.finditer(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/|[{}]',text,re.S)
 blocks=[];depth=0
 for t in tokens:
  if t.group()=='{':
   if not depth:start=text.rfind('\n',0,t.start())+1
   depth+=1
  elif t.group()=='}':
   depth-=1
   if not depth:blocks.append((start,t.end(),text[start:t.end()]))
 for start,end,block in reversed(blocks):
  partition='odm' if 'device_specific: true' in block else 'vendor'
  match=re.search(r'\bname:\s*"([^"]+)"',block)
  original=match.group(1) if match else None
  if original in RENAMES:
   suffix=RENAMES[original] or partition
   block=block[:match.start()]+block[match.start():].replace('name: "'+original+'",','name: "'+original+'_'+suffix+'",\n    stem: "'+original+'",',1)
  # Replace exact dependency names only, not source paths or SONAME stems.
  for name,target in RENAMES.items():
   block=re.sub(r'(?m)^(\s+)"'+re.escape(name)+r'",',lambda m:m.group(1)+'"'+name+'_'+(target or partition)+'",',block)
  text=text[:start]+block+text[end:]
 return text
def fix_mk(text):
 for name,partition in RENAMES.items():
  text=re.sub(r'(?m)^(\s+)'+re.escape(name)+r'(\s*(?:\\)?\s*)$',lambda m:m.group(1)+name+'_'+(partition or 'odm')+m.group(2),text)
 return text
def fix_extract(text):
 if '    private_names = {' in text:return text
 function='''def lib_fixup_camera_partition(lib: str, partition: str, *args, **kwargs):
    # These stock interfaces must not replace same-named system_ext AIDL modules.
    if lib in ('vendor.oplus.hardware.cameraextension-V1-ndk',
               'vendor.oplus.hardware.commondcs-V1-ndk_platform'):
        return f'{lib}_vendor'
    if lib == 'vendor.oplus.hardware.cammidasservice-V1-ndk':
        return f'{lib}_{partition}' if partition in ('odm', 'vendor') else None
    return f'{lib}_odm'


'''
 if 'def lib_fixup_camera_partition(' in text:
  start=text.index('def lib_fixup_camera_partition(');end=text.index('lib_fixups: lib_fixups_user_type = {',start)
  text=text[:start]+function+text[end:]
  if "'vendor.oplus.hardware.commondcs-V1-ndk_platform'" not in text[text.index('lib_fixups: lib_fixups_user_type = {'):]:
   text=text.replace('    ): lib_fixup_camera_partition,', "        'vendor.oplus.hardware.commondcs-V1-ndk_platform',\n    ): lib_fixup_camera_partition,",1)
  return text
 text=text.replace('lib_fixups: lib_fixups_user_type = {',function+'lib_fixups: lib_fixups_user_type = {',1)
 text=text.replace('    **lib_fixups,','    **lib_fixups,\n    (\n'+''.join("        '"+name+"',\n" for name in RENAMES)+'    ): lib_fixup_camera_partition,',1)
 return text

def apply_fix(read,put):
 for path,fn in [('vendor/oneplus/aston/Android.bp',fix_bp),('vendor/oneplus/aston/aston-vendor.mk',fix_mk),('device/oneplus/aston/extract-files.py',fix_extract)]:put(path,fn(read(path)))
