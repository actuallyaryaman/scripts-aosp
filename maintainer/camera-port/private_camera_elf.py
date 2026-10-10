"""Same-length ELF dynamic-string edits. Does not relocate sections or touch code."""
import struct
PRIVATE_CAMERA_NAMES={
 'vendor.oplus.hardware.cammidasservice-V1-ndk.so':'vendor.oplus.hardware.cammidasservice-C1-ndk.so',
 'vendor.oplus.hardware.commondcs-V1-ndk_platform.so':'vendor.oplus.hardware.commondcs-C1-ndk_platform.so',
 'vendor.oplus.hardware.sendextcamcmd-V2-ndk.so':'vendor.oplus.hardware.sendextcamcmd-C2-ndk.so',
}
def elf_dynamic_strings(data):
 if data[:4]!=b'\x7fELF':return []
 if data[4:6]!=b'\x02\x01':raise ValueError('Expected a 64-bit little-endian camera ELF')
 if len(data)<64:raise ValueError('Truncated ELF header')
 phoff=struct.unpack_from('<Q',data,32)[0];ents,num=struct.unpack_from('<HH',data,54)
 if ents<56 or phoff+ents*num>len(data):raise ValueError('Invalid program header table')
 loads=[];dynamic=None
 for i in range(num):
  typ,flags,off,addr,phys,size,mem,align=struct.unpack_from('<IIQQQQQQ',data,phoff+i*ents)
  if off+size>len(data):raise ValueError('Invalid ELF segment bounds')
  if typ==1:loads.append((addr,off,size))
  elif typ==2:dynamic=(off,size)
 if dynamic is None:return []
 off,size=dynamic;tags=[];straddr=strsize=None
 for at in range(off,off+size-15,16):
  tag,value=struct.unpack_from('<qQ',data,at)
  if tag==0:break
  if tag==5:straddr=value
  elif tag==10:strsize=value
  elif tag in (1,14):tags.append((tag,value))
 if straddr is None or strsize is None:raise ValueError('ELF dynamic string table missing')
 offset=next((o+straddr-a for a,o,s in loads if a<=straddr and straddr+strsize<=a+s),None)
 if offset is None:raise ValueError('Invalid dynamic string table address')
 out=[]
 for tag,value in tags:
  if value>=strsize:raise ValueError('Invalid dynamic string offset')
  at=offset+value;end=data.find(b'\0',at,offset+strsize)
  if end<0:raise ValueError('Unterminated dynamic string')
  out.append((tag,at,data[at:end].decode('ascii')))
 return out
def rewrite_camera_elf(data):
 edits={at:(old,PRIVATE_CAMERA_NAMES[old]) for tag,at,old in elf_dynamic_strings(data) if old in PRIVATE_CAMERA_NAMES}
 if not edits:return data
 out=bytearray(data)
 for at,(old,new) in edits.items():
  if len(old)!=len(new):raise ValueError('Private ELF names must have equal byte length')
  out[at:at+len(old)]=new.encode('ascii')
 return bytes(out)
def camera_private_blob_fixup(ctx,file,file_path,*args,**kwargs):
 from pathlib import Path
 path=Path(file_path);before=path.read_bytes();after=rewrite_camera_elf(before)
 if after!=before:path.write_bytes(after)
