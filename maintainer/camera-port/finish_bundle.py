"""Camera-only donor merge and runtime identity hardening; executed by prepare_bundle."""
# DONOR is supplied by prepare_bundle.py.
manifest=json.loads((DATA/'camera-blobs.json').read_text())['files']
destinations={e['destination'] for e in manifest}
# Exact extraction entries, keeping non-camera lines and NFC fixups.
def entry_key(line):
 return line.split('|')[0].split(';')[0].split(':')[-1].lstrip('-')
donor_entries={entry_key(l):l for l in (DONOR.parent/'unused').read_text().splitlines()} if False else {}
for ref in ('b0a4fef','d590273','d012215','f75b8ba'):
 for part in parts(patch(ref)):
  if partfile(part)=='proprietary-files.txt':
   for l in part.splitlines():
    if l.startswith('+') and not l.startswith('+++') and not l.startswith('+#'):
     donor_entries[entry_key(l[1:])]=l[1:]
p='device/oneplus/aston/proprietary-files.txt'
s=read(p);seen=set();out=[]
for l in s.splitlines():
 key=entry_key(l)
 if key in destinations:
  out.append(donor_entries[key]);seen.add(key)
 else:out.append(l)
out+=['','# OnePlus Camera .400 dependencies (pinned, aston only)']+[donor_entries[k] for k in sorted(destinations-seen)]
put(p,'\n'.join(out)+'\n')
p='device/oneplus/aston/extract-files.py'
replace(p,"namespace_imports = [", "namespace_imports = [\n    'device/oneplus/aston',\n    'vendor/oneplus/camera',")
replace(p,"    'odm/etc/camera/CameraHWConfiguration.config': blob_fixup()\n        .regex_replace('SystemCamera =  0;  0;  0;  1;  0;  1;', 'SystemCamera =  0;  0;  0;  0;  0;  0;'),\n",'')
replace(p,".replace_needed('android.hardware.graphics.common-V3-ndk.so', 'android.hardware.graphics.common-V7-ndk.so'),", ".replace_needed('android.hardware.graphics.common-V3-ndk.so', 'android.hardware.graphics.common-V7-ndk.so')\n        .add_needed('libapsfixup.so'),")
# Use upstream extraction substitutions, retaining the device's own entries.
part=next(x for x in parts(patch('d590273')) if partfile(x)=='extract-files.py')
insert=added(part).replace("    'vendor/oplus/camera',\n", '').replace('vendor/oplus/camera','vendor/oneplus/camera')
# The added lines contain the new fixup tuple only.
replace(p,'blob_fixups: blob_fixups_user_type = {','blob_fixups: blob_fixups_user_type = {\n'+insert)
# Keep HIS in the isolated-libui tuple, including its existing symbol fixups.
s=read(p)
s=s.replace("        'odm/lib64/libHIS.so',\n        'odm/lib64/libOGLManager.so',", "        'odm/lib64/libOGLManager.so',")
s=s.replace("        'odm/lib64/libHIS.so',\n", '')
s=s.replace("blob_fixups: blob_fixups_user_type = {\n", "blob_fixups: blob_fixups_user_type = {\n    'odm/lib64/libHIS.so': blob_fixup()\n        .replace_needed('libui.so', 'libui_oplus.so')\n        .clear_symbol_version('AHardwareBuffer_allocate')\n        .clear_symbol_version('AHardwareBuffer_describe')\n        .clear_symbol_version('AHardwareBuffer_lock')\n        .clear_symbol_version('AHardwareBuffer_release')\n        .clear_symbol_version('AHardwareBuffer_unlock'),\n")
put(p,s)
# Parse Blueprint top-level blocks without treating comment/string braces as syntax.
def blocks(s):
 tokens=list(re.finditer(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/|[{}]',s,re.S))
 depth=0;start=0;result=[]
 for t in tokens:
  if t.group()=='{':
   if depth==0:
    start=s.rfind('\n',0,t.start())+1
   depth+=1
  elif t.group()=='}':
   depth-=1
   if depth==0:result.append((start,t.end(),s[start:t.end()]))
 return result
def name(block):
 m=re.search(r'\bname:\s*"([^"]+)"',block);return m.group(1) if m else None
bp=(DONOR/'Android.bp').read_text()
selected={name(b):b for a,z,b in blocks(bp) if any('"proprietary/'+d+'"' in b for d in destinations)}
selected.pop(None,None)
p='vendor/oneplus/aston/Android.bp';s=read(p)
existing={name(b) for a,z,b in blocks(s)}
for a,z,b in reversed(blocks(s)):
 if name(b) in selected:s=s[:a]+selected[name(b)]+s[z:]
s+='\n\n'+'\n\n'.join(selected[n] for n in sorted(selected.keys()-existing))+'\n'
s=s.replace('        "hardware/oplus",','        "hardware/oplus",\n        "device/oneplus/aston",\n        "vendor/oneplus/camera",',1)
put(p,s)
# Merge only copy rules referencing camera assets; package names are de-duplicated.
p='vendor/oneplus/aston/aston-vendor.mk';s=read(p);donormk=(DONOR/'aston-vendor.mk').read_text()
def copykey(l):
 m=re.search(r'vendor/oneplus/aston/proprietary/([^:\s]+):',l);return m.group(1) if m else None
copies={copykey(l):l.strip().rstrip('\\').strip() for l in donormk.splitlines() if copykey(l) in destinations}
lines=[]
for l in s.splitlines():
 k=copykey(l)
 if k in destinations:
  # Preserve list continuation even when this was the last original line.
  if k in copies:lines.append('    '+copies.pop(k)+(' \\' if l.rstrip().endswith('\\') else ''))
  elif l.rstrip().endswith('\\'):continue
  else:lines.append('    # moved to an ELF prebuilt')
 else:lines.append(l)
s='\n'.join(lines)+'\n'
if copies:s+='\nPRODUCT_COPY_FILES += \\\n'+' \\\n'.join('    '+copies[k] for k in sorted(copies))+'\n'
present=set(re.findall(r'^\s+([\w.+@-]+)\s*(?:\\)?$',s,re.M))
s+='\nPRODUCT_PACKAGES += \\\n'+' \\\n'.join('    '+n for n in sorted(selected.keys()-present))+'\n'
put(p,s)
# Complete the listener method on the existing framework stub.
p='hardware/oplus/oplus-fwk/src/android/app/OplusActivityTaskManager.java'
s=read(p)
if 'registerTaskInfoChangeListener' not in s:put(p,s.rsplit('}',1)[0]+'''    public boolean registerTaskInfoChangeListener(com.oplus.app.OplusTaskInfoChangeListener listener,
            int arg1, int arg2) { return false; }
}
''')
# Harden fixed-offset helper: identify ELF before touching any slot and publish originals first.
p='device/oneplus/aston/apsfixup/apsfixup.cpp';s=read(p)
s=s.replace('#include <android/log.h>','#include <android/log.h>\n#include <atomic>\n#include <elf.h>\n#include <link.h>')
a=s.index('static bool module_base(');b=s.index('// True if',a)
s=s[:a]+'''// Offsets are valid only for these exact pinned ELF builds. Unknown builds are ignored.
struct ModuleQuery { const char* name; const char* id; uint64_t base; };
static int find_module(struct dl_phdr_info* info, size_t, void* opaque) {
    auto* q = static_cast<ModuleQuery*>(opaque);
    const char* leaf = strrchr(info->dlpi_name, '/');
    leaf = leaf ? leaf + 1 : info->dlpi_name;
    if (strcmp(leaf, q->name)) return 0;
    for (int i = 0; i < info->dlpi_phnum; ++i) {
        const auto& ph = info->dlpi_phdr[i];
        if (ph.p_type != PT_NOTE) continue;
        const auto* cur = reinterpret_cast<const uint8_t*>(info->dlpi_addr + ph.p_vaddr);
        const auto* end = cur + ph.p_memsz;
        while (size_t(end - cur) >= sizeof(ElfW(Nhdr))) {
            ElfW(Nhdr) note; memcpy(&note, cur, sizeof(note)); cur += sizeof(note);
            size_t names = (size_t(note.n_namesz) + 3) & ~size_t(3);
            size_t descs = (size_t(note.n_descsz) + 3) & ~size_t(3);
            if (names > size_t(end-cur) || descs > size_t(end-cur)-names) break;
            const uint8_t* desc = cur + names;
            if (note.n_type == NT_GNU_BUILD_ID && note.n_namesz == 4 &&
                    !memcmp(cur, "GNU", 4) && strlen(q->id) == note.n_descsz * 2) {
                char hex[129] = {};
                if (note.n_descsz > 64) break;
                for (unsigned j=0; j<note.n_descsz; ++j) snprintf(hex+j*2, 3, "%02x", desc[j]);
                if (!strcmp(hex, q->id)) q->base = info->dlpi_addr;
                else LOGW("unsupported %s build ID %s: hooks disabled", q->name, hex);
                return 1;
            }
            cur += names + descs;
        }
    }
    return 1;
}
static bool module_base(const char* name, uint64_t* out_base) {
    const char* id = !strcmp(name, "libAlgoProcess.so") ?
            "1d7e89c4c5ef30e12443e1e96059321c" : "a0f663b85c6eb794fcf4db20acd8b0c5";
    ModuleQuery q{name, id, 0};
    dl_iterate_phdr(find_module, &q);
    if (!q.base) return false;
    *out_base = q.base;
    return true;
}

'''+s[b:]
a=s.index('static bool got_redirect(');b=s.index('// ── (1)',a)
s=s[:a]+'''template<typename T>
static bool got_redirect(uint64_t slot, void* newval, std::atomic<T>& real, void** old) {
    auto* got = reinterpret_cast<void**>(slot);
    const long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) return false;
    uintptr_t page = slot & ~(uintptr_t(page_size) - 1);
    if (mprotect(reinterpret_cast<void*>(page), page_size, PROT_READ | PROT_WRITE)) return false;
    void* original = __atomic_load_n(got, __ATOMIC_ACQUIRE);
    if (!original || original == newval) {
        mprotect(reinterpret_cast<void*>(page), page_size, PROT_READ);
        return false;
    }
    real.store(reinterpret_cast<T>(original), std::memory_order_release);
    if (old) *old = original;
    __atomic_store_n(got, newval, __ATOMIC_RELEASE);
    if (mprotect(reinterpret_cast<void*>(page), page_size, PROT_READ))
        LOGW("could not restore GOT protection at %p", reinterpret_cast<void*>(page));
    return true;
}

'''+s[b:]
s=re.sub(r'static (\w+_t) (g_real_\w+) = nullptr;',r'static std::atomic<\1> \2{nullptr};',s)
for key in ('p010','memcpy','camlock','uninit','mutex_lock','mutex_unlock','mutex_dtor','dlsym'):
 s=s.replace('g_real_'+key+'(', 'g_real_'+key+'.load(std::memory_order_acquire)(')
 mapping={'p010':'P010','memcpy':'MEMCPY','camlock':'CAMLOCK','uninit':'UNINIT','mutex_lock':'MUTEX_LOCK','mutex_unlock':'MUTEX_UNLOCK','mutex_dtor':'MUTEX_DTOR','dlsym':'DLSYM'}
 s=s.replace('(void*)wrap_'+key+', &old)', '(void*)wrap_'+key+', g_real_'+key+', &old)')
 s=re.sub(r'\s*g_real_'+key+r' = \(\w+_t\)old;', '',s)
s=s.replace('if (!g_real_camlock)   // same real fn as the','// same real fn as the')
s=s.replace('if (!g_real_mutex_lock && got_redirect', 'if (!g_real_mutex_lock && got_redirect')
# Original single-line if bodies became empty after removing late publication.
for key in ('lock','unlock','dtor'):
 s=s.replace('g_real_mutex_'+key+', &old))\n', 'g_real_mutex_'+key+', &old)) {}\n')
# Interface must not use an unverified process body even if only it loaded first.
s=s.replace('if (addr_in_module((uint64_t)*slot, "libAlgoProcess.so") &&', 'uint64_t process_base = 0;\n            if (module_base("libAlgoProcess.so", &process_base) &&\n                *slot == reinterpret_cast<void*>(process_base + CAMLOCK_BODY_OFF) &&')
put(p,s)
p='device/oneplus/aston/apsfixup/Android.bp';replace(p,'shared_libs: ["liblog"]','shared_libs: ["liblog", "libdl"]')
# Existing empty AppInfo needs the Parcelable ABI used by the new camera/task stubs.
part=next(x for x in parts(patch('ee67')) if partfile(x).endswith('/OplusAppInfo.java'))
put('hardware/oplus/'+partfile(part),added(part))
p='hardware/oplus/oplus-fwk/src/android/app/OplusActivityManager.java'
put(p,read(p).rsplit('}',1)[0]+'''    public boolean putConfigInfo(String name, android.os.Bundle data, int flag, int user) throws android.os.RemoteException {
        return false;
    }
    public android.os.Bundle getConfigInfo(String name, int flag, int user) throws android.os.RemoteException { return null; }
}
''')
# Add camera-used Builder APIs while retaining the current haptics Parcelable layout/defaults.
p='hardware/oplus/oplus-fwk/src/com/oplus/os/WaveformEffect.java'
s=read(p);part=next(x for x in parts(patch('ae13')) if partfile(x).endswith('/WaveformEffect.java'))
constants='\n'.join(l for l in added(part).splitlines() if re.match(r'    public static final (int|String) ',l))
s=s.replace('    private static final String TAG',constants+'\n\n    private static final String TAG',1)
for method,typ in [('setAsynchronous','boolean'),('setEffectStrength','int'),('setIsRingtoneCustomized','boolean'),('setRingtoneFilePath','String'),('setRingtoneVibrateType','int'),('setUsageHint','int')]:
 s=s.replace('        public Builder setEffectType(',f'        public Builder {method}({typ} value) {{ return this; }}\n\n        public Builder setEffectType(',1)
put(p,s)
# Install the public-library additions directly for aston; extraction is not run at apply time.
p='vendor/oneplus/sm8550-common/proprietary/vendor/etc/public.libraries.txt'
public=(ROOT/p).read_text().splitlines()
for lib in re.findall(r"\.add_line_if_missing\('([^']+)'\)",read('device/oneplus/sm8550-common/extract-files.py')):
 if lib not in public:public.append(lib)
put('device/oneplus/aston/configs/camera-public.libraries.txt','\n'.join(public)+'\n')
p='device/oneplus/aston/device.mk'
put(p,read(p)+'''\n# Replace the common file only for aston, retaining its existing public sonames.
PRODUCT_COPY_FILES := $(filter-out %:$(TARGET_COPY_OUT_VENDOR)/etc/public.libraries.txt,$(PRODUCT_COPY_FILES))
PRODUCT_COPY_FILES += device/oneplus/aston/configs/camera-public.libraries.txt:$(TARGET_COPY_OUT_VENDOR)/etc/public.libraries.txt
''')
# The common camera exclusion prop already equals the package value; keep it for other products.
p='device/oneplus/sm8550-common/properties/vendor.prop';put(p,(BEFORE/p).read_text())

exec((DATA/'fix_camera_interface_names.py').read_text())
apply_fix(read,put)

exec((DATA/'prepare_private_camera.py').read_text())

# New camera public types have no counterpart in the 202504 system_ext policy API.
put('vendor/oneplus/camera/sepolicy/private/compat/202504/202504.ignore.cil',
    (ROOT/'vendor/oneplus/camera/sepolicy/private/compat/202404/202404.ignore.cil').read_text())
