#!/usr/bin/env bash
# Lindroid guide setup for VoltageOS aston. No compilation, flashing, or commits.
set -euo pipefail
command -v python3 >/dev/null || { echo "Missing python3" >&2; exit 1; }
command -v git >/dev/null || { echo "Missing git" >&2; exit 1; }
python3 - "$@" <<'LINDROID_GUIDE_PY'
PATCHES = {
    'kernel/oneplus/sm8550': r'''diff --git a/arch/arm64/configs/gki_defconfig b/arch/arm64/configs/gki_defconfig
--- a/arch/arm64/configs/gki_defconfig
+++ b/arch/arm64/configs/gki_defconfig
@@ -32,7 +32,7 @@
 CONFIG_CGROUP_CPUACCT=y
 CONFIG_CGROUP_BPF=y
 CONFIG_NAMESPACES=y
-# CONFIG_PID_NS is not set
+CONFIG_PID_NS=y
 CONFIG_RT_SOFTINT_OPTIMIZATION=y
 CONFIG_RELAY=y
 # CONFIG_RD_BZIP2 is not set
@@ -719,3 +719,9 @@
 CONFIG_PID_IN_CONTEXTIDR=y
 CONFIG_FUNCTION_ERROR_INJECTION=y
 # CONFIG_RUNTIME_TESTING_MENU is not set
+CONFIG_SYSVIPC=y
+CONFIG_UTS_NS=y
+CONFIG_IPC_NS=y
+CONFIG_USER_NS=y
+CONFIG_NET_NS=y
+CONFIG_CGROUP_DEVICE=y
diff --git a/arch/arm64/configs/vendor/kalama_GKI.config b/arch/arm64/configs/vendor/kalama_GKI.config
--- a/arch/arm64/configs/vendor/kalama_GKI.config
+++ b/arch/arm64/configs/vendor/kalama_GKI.config
@@ -570,3 +570,4 @@
 # CONFIG_WFX is not set
 # CONFIG_WILC1000_SDIO is not set
 # CONFIG_WILC1000_SPI is not set
+CONFIG_DRM_LINDROID_EVDI=y
diff --git a/drivers/Makefile b/drivers/Makefile
--- a/drivers/Makefile
+++ b/drivers/Makefile
@@ -187,3 +187,4 @@
 obj-$(CONFIG_INTERCONNECT)	+= interconnect/
 obj-$(CONFIG_COUNTER)		+= counter/
 obj-$(CONFIG_MOST)		+= most/
+obj-y += lindroid-drm/
diff --git a/drivers/Kconfig b/drivers/Kconfig
--- a/drivers/Kconfig
+++ b/drivers/Kconfig
@@ -236,4 +236,5 @@
 source "drivers/counter/Kconfig"
 
 source "drivers/most/Kconfig"
+source "drivers/lindroid-drm/Kconfig"
 endmenu
diff --git a/fs/overlayfs/util.c b/fs/overlayfs/util.c
--- a/fs/overlayfs/util.c
+++ b/fs/overlayfs/util.c
@@ -148,9 +148,7 @@
 		return true;
 
 	return dentry->d_flags & (DCACHE_NEED_AUTOMOUNT |
-				  DCACHE_MANAGE_TRANSIT |
-				  DCACHE_OP_HASH |
-				  DCACHE_OP_COMPARE);
+				  DCACHE_MANAGE_TRANSIT);
 }
 
 enum ovl_path_type ovl_path_type(struct dentry *dentry)
''',
    'device/oneplus/aston': r'''diff --git a/device.mk b/device.mk
--- a/device.mk
+++ b/device.mk
@@ -100,3 +100,8 @@
 
 # Inherit from the proprietary files makefile.
 $(call inherit-product, vendor/oneplus/aston/aston-vendor.mk)
+
+# Lindroid: experimental userdebug integration.
+ifeq ($(TARGET_BUILD_VARIANT),userdebug)
+$(call inherit-product, vendor/lindroid/lindroid.mk)
+endif
diff --git a/BoardConfig.mk b/BoardConfig.mk
--- a/BoardConfig.mk
+++ b/BoardConfig.mk
@@ -31,3 +31,8 @@
 
 # Include the proprietary files BoardConfig.
 include vendor/oneplus/aston/BoardConfigVendor.mk
+
+# Lindroid daemon is installed in system_ext; keep its policy in that partition.
+ifeq ($(TARGET_BUILD_VARIANT),userdebug)
+SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += vendor/lindroid/sepolicy
+endif
''',
    'frameworks/base': r'''diff --git a/services/core/java/com/android/server/ExtconStateObserver.java b/services/core/java/com/android/server/ExtconStateObserver.java
--- a/services/core/java/com/android/server/ExtconStateObserver.java
+++ b/services/core/java/com/android/server/ExtconStateObserver.java
@@ -53,6 +53,9 @@
     public void onUEvent(ExtconInfo extconInfo, UEvent event) {
         if (LOG) Slog.d(TAG, extconInfo.getName() + " UEVENT: " + event);
         String name = event.get("NAME");
+        if (name == null) {
+            return;
+        }
         S state = parseState(extconInfo, event.get("STATE"));
         if (state != null) {
             updateState(extconInfo, name, state);
diff --git a/services/core/java/com/android/server/WiredAccessoryManager.java b/services/core/java/com/android/server/WiredAccessoryManager.java
--- a/services/core/java/com/android/server/WiredAccessoryManager.java
+++ b/services/core/java/com/android/server/WiredAccessoryManager.java
@@ -556,6 +556,9 @@
 
             if (name == null) {
                 name = event.get("SWITCH_NAME");
+                if (name == null) {
+                    return;
+                }
             }
 
             try {
''',
    'frameworks/native': r'''diff --git a/services/inputflinger/reader/EventHub.cpp b/services/inputflinger/reader/EventHub.cpp
--- a/services/inputflinger/reader/EventHub.cpp
+++ b/services/inputflinger/reader/EventHub.cpp
@@ -2570,6 +2570,13 @@
     // Obtain the associated device, if any.
     device->associatedDevice = obtainAssociatedDeviceLocked(devicePath, device->configuration);
 
+    // Disable device if device config property set.
+    if (device->configuration &&
+        device->configuration->getBool("device.disabled").value_or(false)) {
+        device->disable();
+        ALOGV("Disabling device with id %d\n", device->id);
+    }
+
     // Figure out the kinds of events the device reports.
     device->readDeviceBitMask(EVIOCGBIT(EV_KEY, 0), device->keyBitmask);
     device->readDeviceBitMask(EVIOCGBIT(EV_ABS, 0), device->absBitmask);
''',
    'external/libhybris': r'''diff --git a/compat/camera/Android.mk b/compat/camera/Android.mk.disabled
similarity index 100%
rename from compat/camera/Android.mk
rename to compat/camera/Android.mk.disabled
diff --git a/compat/hwc2/Android.mk b/compat/hwc2/Android.mk.disabled
similarity index 100%
rename from compat/hwc2/Android.mk
rename to compat/hwc2/Android.mk.disabled
diff --git a/compat/input/Android.mk b/compat/input/Android.mk.disabled
similarity index 100%
rename from compat/input/Android.mk
rename to compat/input/Android.mk.disabled
diff --git a/compat/media/Android.mk b/compat/media/Android.mk.disabled
similarity index 100%
rename from compat/media/Android.mk
rename to compat/media/Android.mk.disabled
diff --git a/compat/surface_flinger/Android.mk b/compat/surface_flinger/Android.mk.disabled
similarity index 100%
rename from compat/surface_flinger/Android.mk
rename to compat/surface_flinger/Android.mk.disabled
diff --git a/compat/ui/Android.mk b/compat/ui/Android.mk.disabled
similarity index 100%
rename from compat/ui/Android.mk
rename to compat/ui/Android.mk.disabled
diff --git a/compat/ui/Android.bp b/compat/ui/Android.bp
new file mode 100644
--- /dev/null
+++ b/compat/ui/Android.bp
@@ -0,0 +1,21 @@
+// Android 17 Soong equivalent of the upstream UI compatibility library.
+// The other legacy compatibility modules are not used by Lindroid's product.
+cc_library_shared {
+    name: "libui_compat_layer",
+    srcs: ["ui_compatibility_layer.cpp"],
+    include_dirs: ["external/libhybris/hybris/include"],
+    shared_libs: [
+        "libcutils",
+        "libutils",
+        "libbinder",
+        "libhardware",
+        "liblog",
+        "libui",
+        "libhidlbase",
+    ],
+    cflags: [
+        "-DANDROID_VERSION_MAJOR=17",
+        "-DANDROID_VERSION_MINOR=0",
+        "-DANDROID_VERSION_PATCH=0",
+    ],
+}
''',
    'vendor/lindroid': r'''diff --git a/interfaces/composer/Android.bp b/interfaces/composer/Android.bp
--- a/interfaces/composer/Android.bp
+++ b/interfaces/composer/Android.bp
@@ -3,7 +3,7 @@
     system_ext_specific: true,
     srcs: [ "vendor/lindroid/composer/*.aidl" ],
     imports: [
-        "android.hardware.graphics.common-V5",
+        "android.hardware.graphics.common-V7",
     ],
 
     unstable: true,
diff --git a/sepolicy/perspectived.te b/sepolicy/perspectived.te
--- a/sepolicy/perspectived.te
+++ b/sepolicy/perspectived.te
@@ -17,7 +17,7 @@
 allow perspectived self:capability { net_admin chown fsetid fowner sys_admin sys_resource kill };
 
 allow perspectived init:file r_file_perms;
-allow perspectived init:dir w_dir_perms;
+allow perspectived init:dir r_dir_perms;
 
 allow perspectived shell_exec:file rx_file_perms;
 
diff --git a/lindroid.mk b/lindroid.mk
--- a/lindroid.mk
+++ b/lindroid.mk
@@ -46,6 +46,3 @@
     $(LOCAL_PATH)/configs/disabled.idc:$(TARGET_COPY_OUT_SYSTEM)/usr/idc/Vendor_000a_Product_000b.idc \
     $(LOCAL_PATH)/configs/disabled.idc:$(TARGET_COPY_OUT_SYSTEM)/usr/idc/Vendor_000a_Product_000c.idc \
     $(LOCAL_PATH)/configs/disabled.idc:$(TARGET_COPY_OUT_SYSTEM)/usr/idc/Vendor_000a_Product_000d.idc
-
-BOARD_SEPOLICY_DIRS += \
-       vendor/lindroid/sepolicy
''',
}
import argparse
import difflib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

GUIDE = "https://www.lindroid.org/"
DEPS = {
    "kernel/oneplus/sm8550/drivers/lindroid-drm": ("lindroid-drm-loopback", "d3b85f3251beae4bc8481538f37d13b7f30abde0"),
    "vendor/lindroid": ("vendor_lindroid", "eadbb70f13209133d96a5355464388db8c6578de"),
    "external/lxc": ("external_lxc", "4e3a3630fff3dc04e0d4a761309f87f248e40b17"),
    "external/libhybris": ("libhybris", "29e0fa6da0166261f6b9437582fe2d56bab8530c"),
}

parser = argparse.ArgumentParser(
    prog="setup-lindroid.sh",
    description="Apply only the Lindroid guide's patches and dependencies for aston.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""Run from the ROM root:
  bash rom-tools/scripts/features/setup-lindroid.sh --check .   # offline patch checks; no source changes
  bash rom-tools/scripts/features/setup-lindroid.sh .           # fetch pinned dependencies, then apply
  bash rom-tools/scripts/features/setup-lindroid.sh --fix-fcm . # additionally remove the SYSVIPC FCM restriction

Source references:
  Guide: https://www.lindroid.org/
  Official pinned message: https://t.me/linux_on_droid/1263
  Soft reboot: https://t.me/linux_on_droid/10346
    https://gerrit.libremobileos.com/c/LMODroid/platform_frameworks_base/+/16080
    revision 1bb15b742019e9f54152b6ef3a7708495879b0fc
  OverlayFS: https://github.com/android-kxxt/android_kernel_xiaomi_sm8450/commit/ae700d3d04a2cd8b34e1dae434b0fdc9cde535c7
  Input: https://review.lineageos.org/c/LineageOS/android_frameworks_native/+/436710
    revision 382a0f5dcae542f571d329222ec662d1df7b8108
    Author: Billy Laws. Upstream change is abandoned, but explicitly in your guide.
    Adaptation: read std::optional<bool> with value_or(false), preserving its intent.
  Dependency source: https://github.com/Linux-on-droid/

Scope:
  Patches kernel/oneplus/sm8550, device/oneplus/aston, frameworks/base,
  frameworks/native, the libhybris build definitions, and the Lindroid composer
  AIDL import (graphics.common V5 -> V7 to match this ROM). Lindroid policy
  restricts init:dir to r_dir_perms to satisfy the observed neverallow.
  Policy registration is moved from BOARD_SEPOLICY_DIRS in lindroid.mk to
  SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS in aston BoardConfig.mk (userdebug only),
  matching the daemon installation partition and satisfying Treble labeling.
  The six legacy
  compat Android.mk files are preserved as Android.mk.disabled. The required
  libui_compat_layer gets an Android 17 Android.bp; libhwc2_compat_layer already
  has an upstream Android.bp in compat/apphwc. The global denylist is unchanged.
  Four pinned dependencies are standalone Git checkouts;
  no repo manifest is created and no repo sync is run. Existing dependency
  checkouts must be at, or descended from, the pinned revision.
  The nine guide options go in gki_defconfig and vendor/kalama_GKI.config;
  driver registration uses obj-y as specified. Product inheritance is userdebug
  only. The kernel defconfig changes themselves are shared by all builds using
  these configs. OverlayFS hack is included because this ROM enables casefold.
  This bypass does not implement full case-insensitive OverlayFS support;
  Lindroid rootfs/upper/work directories must remain case-sensitive.
  NixOS-only TMPFS_POSIX_ACL is not added.
  --fix-fcm is ONLY for a reported CONFIG_SYSVIPC FCM requirement failure.
  It removes the exact '# CONFIG_SYSVIPC is not set' line from
  kernel/configs/*/*/android-base.config, following the guide.

Limits:
  No extra ABI/export changes or source API changes are added. The init:dir
  policy fix restricts permissions; global SELinux and neverallows are unchanged.
  The libhybris build-definition conversion fixes the blocked-Android.mk error;
  the composer V7 import fixes the observed V5/V7 AIDL dependency conflict.
  These pinned upstream dependencies may need Android-version compatibility
  fixes in this Android 17 tree. Applying this script does not prove that the
  ROM builds or Lindroid runs. Build and device testing are yours to perform.
  Script performs NO compilation, flashing, commits, resets, or repo sync.
  Repeated application skips file patches already present, including those
  from earlier script versions. Conflicting/partial file patches fail before
  source edits. Network failures leave sources untouched.
  Unexpected write failures can leave partial changes; no automatic reset.
  Downloaded dependencies stay on disk after success and are not maintained
  by repo sync. Review git diff and git status before committing manually.
""",
)
parser.add_argument("--check", action="store_true", help="offline checks, no fetch or apply")
parser.add_argument("--fix-fcm", action="store_true", help="opt-in documented SYSVIPC FCM workaround")
parser.add_argument("root", nargs="?", default=".", help="Android source root (default: current directory)")
args = parser.parse_args()
root = Path(args.root).resolve()
if not (root / ".repo").is_dir():
    parser.error("Not an Android repo checkout: " + str(root))


def git(path, *argv, data=None, check=True):
    return subprocess.run(["git", "-C", str(path), *argv], input=data, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def fail(message):
    raise RuntimeError(message)


def preflight(repo, patch, path=None):
    path = root / repo if path is None else path
    if not (path / ".git").exists():
        fail("Missing Git repository: " + repo)
    # Check file patches independently so newer script fixes can be added to
    # an installation made by an earlier script without reapplying old edits.
    remaining = []
    for block in patch.split("diff --git ")[1:]:
        file_patch = "diff --git " + block
        if git(path, "apply", "--reverse", "--check", "-", data=file_patch,
               check=False).returncode == 0:
            continue
        result = git(path, "apply", "--check", "-", data=file_patch, check=False)
        if result.returncode:
            fail("Conflicting or partial patch in " + repo + ":\n" + result.stderr)
        remaining.append(file_patch)
    print(("Compatible: " if remaining else "Already applied: ") + repo, flush=True)
    return "".join(remaining)


def check_dependency(path, pin):
    if not (path / ".git").exists():
        fail("Dependency path is not a Git checkout: " + str(path))
    if git(path, "merge-base", "--is-ancestor", pin, "HEAD", check=False).returncode:
        fail("Dependency is not based on pinned revision " + pin + ": " + str(path))


try:
    patches = dict(PATCHES)
    if args.fix_fcm:
        fcm = ""
        for path in sorted((root / "kernel/configs").glob("*/*/android-base.config")):
            before = path.read_text()
            after = "".join(line for line in before.splitlines(keepends=True)
                            if line.rstrip("\r\n") != "# CONFIG_SYSVIPC is not set")
            if before != after:
                rel = path.relative_to(root / "kernel/configs").as_posix()
                fcm += "diff --git a/" + rel + " b/" + rel + "\n"
                fcm += "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                               fromfile="a/" + rel, tofile="b/" + rel))
        if fcm:
            patches["kernel/configs"] = fcm
        else:
            print("FCM: no SYSVIPC restriction lines found.", flush=True)
    pending = {repo: preflight(repo, patch) for repo, patch in patches.items()
               if repo not in DEPS or (root / repo).exists()}
    missing = []
    for rel, (_, pin) in DEPS.items():
        path = root / rel
        if path.exists() or path.is_symlink():
            if path.is_symlink():
                fail("Dependency path is a symlink: " + rel)
            check_dependency(path, pin)
        else:
            missing.append(rel)
    if args.check:
        if missing:
            print("Patch checks passed; dependencies not installed: " + ", ".join(missing))
            print("No source changes made. Default invocation will fetch them.")
            sys.exit(1)
        print("All patch/dependency checks passed; no source changes made.")
        sys.exit(0)

    with tempfile.TemporaryDirectory(prefix="lindroid-guide-") as scratch:
        downloads = {}
        for index, rel in enumerate(missing):
            name, pin = DEPS[rel]
            dest = Path(scratch) / str(index)
            print("Fetching " + name + " at " + pin, flush=True)
            subprocess.run(["git", "init", "--quiet", str(dest)], check=True)
            git(dest, "remote", "add", "origin", "https://github.com/Linux-on-droid/" + name + ".git")
            subprocess.run(["git", "-C", str(dest), "fetch", "--depth=1", "origin", pin], check=True)
            git(dest, "checkout", "--detach", pin)
            check_dependency(dest, pin)
            downloads[rel] = dest
        # Recheck after downloads, before moving any checkout or applying patches.
        pending = {repo: preflight(repo, patch, downloads.get(repo))
                   for repo, patch in patches.items()}
        for rel, (_, pin) in DEPS.items():
            if rel not in downloads:
                check_dependency(root / rel, pin)
            elif (root / rel).exists():
                fail("Dependency appeared while downloading: " + rel)
        for rel, dest in downloads.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(target))
            print("Installed dependency: " + rel, flush=True)
        for repo, patch in patches.items():
            if pending[repo]:
                git(root / repo, "apply", "-", data=pending[repo])
                print("Applied: " + repo, flush=True)
    print("Lindroid guide changes applied. No compilation, flashing, or commits performed.")
    print("Review git diff in the patched repos and git status in the new dependencies.")
    print("Libhybris build definitions converted; C++ API/runtime compatibility remains unverified.")
except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
    details = getattr(error, "stderr", None)
    print("ERROR: " + str(error) + ("\n" + details if details else ""), file=sys.stderr)
    sys.exit(1)

LINDROID_GUIDE_PY
