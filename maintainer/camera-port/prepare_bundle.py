#!/usr/bin/env python3
"""Maintainer-only bundle generator; writes a scratch candidate, never live ROM source."""
from pathlib import Path
import json,re,subprocess,tempfile,shutil,hashlib,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', required=True, type=Path)
parser.add_argument('--donor', required=True, type=Path)
parser.add_argument('--staging', type=Path)
args=parser.parse_args()
ROOT=args.root.resolve()
DONOR=args.donor.resolve()
DATA=Path(__file__).resolve().parent
UP=json.loads((DATA/'upstream.json').read_text())['patches']
WORK=args.staging.resolve() if args.staging else Path(tempfile.mkdtemp(prefix='aston-camera-bundle-'))
if WORK.exists() and any(WORK.iterdir()):
 raise SystemExit('Staging directory must be empty')
WORK.mkdir(parents=True,exist_ok=True)
BEFORE=WORK/'before';AFTER=WORK/'after'
FILES=set()
def prime(path):
 if path in FILES:return
 FILES.add(path);src=ROOT/path
 if src.is_file():
  for base in (BEFORE,AFTER):
   out=base/path;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
def put(path,text):
 prime(path);p=AFTER/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
def read(path):prime(path);return (AFTER/path).read_text()
def replace(path,old,new):
 s=read(path)
 if s.count(old)!=1:raise RuntimeError(f'{path}: expected one anchor {old[:80]!r}, found {s.count(old)}')
 put(path,s.replace(old,new,1))
def patch(ref):return (DATA/next(e['file'] for e in UP if e['commit'].startswith(ref))).read_text()
def parts(s):return s.split('diff --git ')[1:]
def partfile(part):return part.splitlines()[0].split(' b/',1)[1]
def added(part):return '\n'.join(l[1:] for l in part.splitlines() if l.startswith('+') and not l.startswith('+++'))+'\n'
for e in UP:
 if e['repo']=='camera-reference-only':continue
 for part in parts((DATA/e['file']).read_text()):prime(e['repo']+'/'+partfile(part))
for repo in dict.fromkeys(e['repo'] for e in UP if e['repo']!='camera-reference-only'):
 path=AFTER/repo;path.mkdir(parents=True,exist_ok=True);subprocess.run(['git','init','-q',str(path)],check=True)
for e in UP:
 if e['repo']=='camera-reference-only':continue
 repo=e['repo'];text=(DATA/e['file']).read_text()
 # Existing classes are merged below; absent classes may be imported without replacing them.
 if e['commit'].startswith(('ee67','5b9f','ae13')):
  for part in parts(text):
   name=repo+'/'+partfile(part)
   if 'new file mode' in part and not (AFTER/name).exists():put(name,added(part))
  if e['commit'].startswith('ae13'):
   for part in parts(text):
    if Path(partfile(part)).name in ('OplusWhiteListManager.java','OplusCameraManager.java'):
     single='diff --git '+part
     r=subprocess.run(['git','-C',str(AFTER/repo),'apply','--whitespace=nowarn','-'],input=single,text=True,capture_output=True)
     if r.returncode:raise RuntimeError(r.stderr)
  continue
 if e['commit'].startswith(('1e800','0cdcc')):continue
 r=subprocess.run(['git','-C',str(AFTER/repo),'apply','--reject','--whitespace=nowarn','-'],input=text,text=True,capture_output=True)
 if r.returncode and not e['commit'].startswith('89dc'):raise RuntimeError(e['commit']+' '+r.stderr)
# Explicit merges preserve the existing implementations and haptics defaults.
p='hardware/oplus/oplus-fwk/src/android/hardware/camera2/IOplusCameraManager.java'
part=next(x for x in parts(patch('ae13')) if partfile(x).endswith('IOplusCameraManager.java'))
replace(p,'        CMD_READ_MEM\n',added(part).rstrip()+'\n')
p='hardware/oplus/oplus-fwk/src/android/view/OplusWindowManager.java'
replace(p,'    public void requestKeyguard(String command) {}','    public void requestKeyguard(String command) {}\n\n    public boolean setPreferredDisplayMode(int mode) { return false; }')
p='hardware/oplus/oplus-fwk/src/com/oplus/osense/OsenseResEventClient.java'
s=read(p);put(p,s.rsplit('}',1)[0]+'''    public int registerEventCallback(com.oplus.osense.eventinfo.OsenseEventCallback callback,
            com.oplus.osense.eventinfo.EventConfig config) { return 0; }
    public int unregisterEventCallback(com.oplus.osense.eventinfo.OsenseEventCallback callback,
            com.oplus.osense.eventinfo.EventConfig config) { return 0; }
}
''')
for suffix in ['com/oplus/osense/eventinfo/EventConfig.java','com/oplus/uah/UAHResClient.java']:
 part=next(x for x in parts(patch('ae13')) if partfile(x).endswith(suffix));p='hardware/oplus/'+partfile(part)
 r=subprocess.run(['git','-C',str(AFTER/'hardware/oplus'),'apply','--whitespace=nowarn','-'],input='diff --git '+part,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr)
p='hardware/oplus/oplus-fwk/src/com/oplus/content/OplusFeatureConfigManager.java'
put(p,read(p).rsplit('}',1)[0]+'''    public boolean isPermit(String name) { return true; }
    public boolean registerFeatureActionObserver(OnFeatureActionObserver observer) { return true; }
    public interface OnFeatureActionObserver {
        default void onFeaturesActionUpdate(String action, String value,
                IOplusFeatureConfigManager.FeatureID id) {}
    }
}
''')
# Camera policy migration must leave all other products' original policy intact.
for part in parts(patch('1e800')):
 p='hardware/oplus/'+partfile(part);prime(p);original=(BEFORE/p).read_text()
 if 'deleted file mode' in part:updated=''
 else:
  r=subprocess.run(['git','-C',str(AFTER/'hardware/oplus'),'apply','--reject','--whitespace=nowarn','-'],input='diff --git '+part,text=True,capture_output=True)
  updated=read(p)
  if r.returncode:
   removed={l[1:] for l in part.splitlines() if l.startswith('-') and not l.startswith('---')}
   updated='\n'.join(l for l in updated.splitlines() if l not in removed)+'\n'
 put(p,"ifelse(target_has_opluscamera, `true', `\n"+updated+"', `\n"+original+"')\n")
# Correct vendor package paths without regenerating its handwritten makefiles.
package=ROOT/'vendor/oneplus/camera'
for p in package.rglob('*'):
 if p.is_file() and '.git' not in p.parts and p.suffix in ('.mk','.bp'):
  name=str(p.relative_to(ROOT));s=p.read_text();put(name,s.replace('vendor/oplus/camera','vendor/oneplus/camera'))
put('vendor/oneplus/camera/vendorsetup.sh','# Platform-signed apps and bootclasspath stubs use scoped hidden-API access.\n')
p='vendor/oneplus/camera/sepolicy/vendor/hal_camera_default.te'
put(p,read(p)+'\nr_dir_file(hal_camera_default, vendor_persist_camera_file)\n')
p='vendor/oneplus/camera/sepolicy/private/property_contexts'
put(p,read(p)+'\nro.camera.oplus_port    u:object_r:exported_system_prop:s0\n')
p='vendor/oneplus/camera/camera-vendor.mk'
put(p,read(p)+'''\n# Enabled exclusively by the aston product.
$(call soong_config_set_bool,camera,oplus_port,true)
PRODUCT_PRODUCT_PROPERTIES += ro.camera.oplus_port=true
''')
# Device-specific build wiring, retaining the existing aston extraction/NFC setup.
p='device/oneplus/aston/device.mk'
put(p,read(p)+'''\n# OnePlus Camera port (aston only).
$(call inherit-product, vendor/oneplus/camera/camera-vendor.mk)
PRODUCT_PACKAGES += libapsfixup sr_models.bin_symlink sr_ref_models.bin_symlink
''')
p='device/oneplus/aston/BoardConfig.mk';put(p,read(p)+'\nTARGET_USES_OPLUS_CAMERA := true\nBUILD_BROKEN_VENDOR_PROPERTY_NAMESPACE := true\n')
p='device/oneplus/aston/Android.bp';replace(p,'        "hardware/oplus",','        "hardware/oplus",\n        "vendor/oneplus/camera",')
sr=next(x for x in parts(patch('f75b8ba')) if partfile(x)=='Android.bp');put(p,read(p)+'\n'+added(sr))
# Extract only the camera helper's source; no astonc paths/configuration are imported.
for part in parts(patch('b0a4fef')):
 if partfile(part).startswith('apsfixup/'):
  put('device/oneplus/aston/'+partfile(part),added(part))
# Repair the rejected camera-service overload at its stable declaration boundary.
p='frameworks/av/services/camera/libcameraservice/device3/Camera3OutputUtils.cpp'
rej=AFTER/(p+'.rej');replace(p,'void notifyShutter(',added(rej.read_text())+'\nvoid notifyShutter(')
replace(p,'!(request.stillCapture || request.hasInputBuffer);','!((request.zslCapture && request.stillCapture) || request.hasInputBuffer);')
# Opt-in gates: no global Binder size or camera teardown change for other products.
p='frameworks/native/libs/binder/ProcessState.cpp'
replace(p,'#define BINDER_VM_SIZE ((4 * 1024 * 1024) - sysconf(_SC_PAGE_SIZE) * 2)', '#if defined(__ANDROID__) && defined(OPLUS_CAMERA_PORT)\n#define BINDER_VM_SIZE ((4 * 1024 * 1024) - sysconf(_SC_PAGE_SIZE) * 2)\n#else\n#define BINDER_VM_SIZE ((1 * 1024 * 1024) - sysconf(_SC_PAGE_SIZE) * 2)\n#endif')
p='frameworks/native/libs/binder/Android.bp'
replace(p,'        "-DBINDER_WITH_KERNEL_IPC",\n    ] + select(', '        "-DBINDER_WITH_KERNEL_IPC",\n    ] + select(soong_config_variable("camera", "oplus_port"), {\n        true: ["-DOPLUS_CAMERA_PORT"],\n        default: [],\n    }) + select(')
p='frameworks/av/services/camera/libcameraservice/CameraService.cpp'
s=read(p);a=s.index('        // --- OPLUS PORT:');b=s.index('        // -----------------------------------------------------------------------',a);s=s[:a]+'        if (property_get_bool("ro.camera.oplus_port", false)) {\n'+s[a:b]+'        }\n'+s[b:]
if '#include <cutils/properties.h>' not in s:s='#include <cutils/properties.h>\n'+s
put(p,s)
p='frameworks/av/services/camera/libcameraservice/api2/CameraDeviceClient.cpp'
replace(p,'if (pkgName != "com.oplus.camera") {','if (property_get_bool("ro.camera.oplus_port", false) && pkgName != "com.oplus.camera") {')
if '#include <cutils/properties.h>' not in read(p):put(p,'#include <cutils/properties.h>\n'+read(p))
p='frameworks/base/services/core/java/com/android/server/wm/ActivityStarter.java'
replace(p,'if (isOplusFileBrowse && isTrustedOplusCaller) {','if (android.os.SystemProperties.getBoolean("ro.camera.oplus_port", false)\n                    && isOplusFileBrowse && isTrustedOplusCaller) {')
p='frameworks/av/media/libmediaplayerservice/StagefrightRecorder.cpp'
replace(p,'status_t StagefrightRecorder::reset() {','status_t StagefrightRecorder::reset() {\n    mOplusUserData.clear();')
p='device/oneplus/sm8550-common/properties/vendor.prop';put(p,'\n'.join(l for l in read(p).splitlines() if not l.startswith('vendor.camera.aux.packageexcludelist='))+'\n')
# Prevent optional camera types from appearing in non-camera DSP policy.
p='device/qcom/sepolicy_vndr/sm8550/generic/vendor/common/domain.te'
s=read(p).replace('- opluscamera_app',"ifelse(target_has_opluscamera, `true', `- opluscamera_app')");put(p,s)
exec((DATA/'finish_bundle.py').read_text())
# The product camera app is a platform domain. Keep access to specifically
# labeled camera data/properties rather than generic vendor defaults.
p='vendor/oneplus/camera/sepolicy/private/opluscamera_app.te'
put(p,'# Installed on /product; declare platform membership in platform policy.\ntypeattribute opluscamera_app coredomain;\n\n'+read(p))
p='vendor/oneplus/camera/sepolicy/vendor/opluscamera_app.te'
for rule in (
 'allow opluscamera_app vendor_data_file:dir  { read open search write add_name remove_name create getattr rename setattr reparent rmdir };\n',
 'allow opluscamera_app vendor_data_file:file { read open write create unlink getattr rename setattr };\n',
 'allow opluscamera_app vendor_default_prop:file { open read getattr map };\n',
):
 replace(p,rule,'')
# Camera compatibility wrappers live in the existing oplus-fwk bootclasspath jar.
p='build/soong/scripts/check_boot_jars/package_allowed_list.txt'
put(p,read(p)+'\n# OnePlus camera compatibility wrappers\ncom\\.color\\.inner\\.content\\.res\ncom\\.color\\.inner\\.view\n')
# No source is written; stage paths and review diff are exported for the generator.
(WORK/'files.json').write_text(json.dumps(sorted(FILES)))
print(WORK)
