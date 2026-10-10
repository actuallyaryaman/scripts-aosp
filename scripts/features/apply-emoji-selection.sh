#!/usr/bin/env bash
# Usage: bash rom-tools/scripts/features/apply-emoji-selection.sh .
# Adds Stock/iOS/Samsung/SwiftUI/Facebook selection in Powerhub Themes.
# Requires clean target repos, Bash, Git, curl, sha256sum, mktemp and cp.
# Downloads pinned fonts before applying; no commits, sync, branches or builds.
# Run again for a no-op. Incompatible patches stop before source changes.
# Sources: framework 18245c13bd6f / 3c8e13e75578 (Pranav Praveen, Ghosuto),
# picker f8116345e5b1 / 3cea0953e3d0; font revision is pinned below.
# Existing license headers and font binaries/metadata remain unchanged.
# Property: persist.sys.voltage_emoji_style; old selection is not migrated.
# Font licenses are independent of code licenses. Test/build on device yourself.
set -euo pipefail

fail() { echo "Emoji selection: $*" >&2; exit 1; }
check_only=0
case "${1:-}" in
    --check) check_only=1; shift ;;
    --help|-h) echo 'Usage: apply-emoji-selection.sh [--check] [ROM_ROOT]'; exit 0 ;;
esac
[[ $# -le 1 ]] || fail "Usage: bash rom-tools/scripts/features/apply-emoji-selection.sh [--check] [ROM_ROOT]"
root=$(cd -- "${1:-.}" && pwd)
for tool in git sha256sum cp curl mktemp; do
    command -v "$tool" >/dev/null || fail "Required command missing: $tool"
done

bundle=$(mktemp -d "${TMPDIR:-/tmp}/emoji-selection.XXXXXXXX")
trap 'rm -rf -- "$bundle"' EXIT
mkdir -p -- "$bundle/patches" "$bundle/fonts"
cat > "$bundle/patches/frameworks-base.patch" <<'EMOJI_FRAMEWORKS_BASE_PATCH'
diff --git a/core/tests/coretests/src/android/graphics/TypefaceSystemFallbackTest.java b/core/tests/coretests/src/android/graphics/TypefaceSystemFallbackTest.java
index 2a25dabb5f1c..557a44dbb5f1 100644
--- a/core/tests/coretests/src/android/graphics/TypefaceSystemFallbackTest.java
+++ b/core/tests/coretests/src/android/graphics/TypefaceSystemFallbackTest.java
@@ -57,6 +57,7 @@ import java.nio.charset.StandardCharsets;
 import java.nio.file.Files;
 import java.nio.file.StandardCopyOption;
 import java.util.HashMap;
+import java.util.List;
 import java.util.Locale;
 import java.util.Map;
 
@@ -941,6 +942,39 @@ public class TypefaceSystemFallbackTest {
         return String.format(xml, op, lang, font);
     }
 
+    @Test
+    public void testBuildSystemFallback_multipleCustomizations() throws Exception {
+        final String oemXml = "<fonts-modification version='1'>"
+                + "<family customizationType='new-named-family' name='google-sans'>"
+                + "<font>b3em.ttf</font></family>"
+                + "<alias name='google-sans-alias' to='google-sans'/>"
+                + "</fonts-modification>";
+        final File emojiXml = new File(TEST_OEM_DIR, "emoji_customization.xml");
+        Files.write(new File(TEST_FONTS_XML).toPath(),
+                getBaseXml("a3em.ttf", "und-Zsye").getBytes(StandardCharsets.UTF_8));
+        Files.write(new File(TEST_OEM_XML).toPath(), oemXml.getBytes(StandardCharsets.UTF_8));
+        Files.write(emojiXml.toPath(),
+                getCustomizationXml("c3em.ttf", "prepend", "und-Zsye")
+                        .getBytes(StandardCharsets.UTF_8));
+        try {
+            FontConfig config = FontListParser.parseWithCustomizations(
+                    TEST_FONTS_XML, TEST_FONT_DIR,
+                    List.of(TEST_OEM_XML, emojiXml.getAbsolutePath() + ".missing",
+                            emojiXml.getAbsolutePath()), TEST_OEM_DIR, null, 0, 0);
+            Map<String, FontFamily[]> fallback = SystemFonts.buildSystemFallback(config);
+            Map<String, Typeface> fonts = SystemFonts.buildSystemTypefaces(config, fallback);
+            Paint paint = new Paint();
+            assertNotNull(fonts.get("named-family"));
+            paint.setTypeface(fonts.get("named-family"));
+            assertEquals(GLYPH_3EM_WIDTH, paint.measureText("c"), 0.0f);
+            assertNotNull(fonts.get("google-sans-alias"));
+            paint.setTypeface(fonts.get("google-sans-alias"));
+            assertEquals(GLYPH_3EM_WIDTH, paint.measureText("b"), 0.0f);
+        } finally {
+            emojiXml.delete();
+        }
+    }
+
     @Test
     public void testBuildSystemFallback__Customization_locale_prepend() {
         final ArrayMap<String, Typeface> fontMap = new ArrayMap<>();
diff --git a/graphics/java/android/graphics/FontListParser.java b/graphics/java/android/graphics/FontListParser.java
index 72760a23ffed..60a97dfa8f2d 100644
--- a/graphics/java/android/graphics/FontListParser.java
+++ b/graphics/java/android/graphics/FontListParser.java
@@ -39,6 +39,7 @@ import java.io.IOException;
 import java.io.InputStream;
 import java.util.ArrayList;
 import java.util.Collections;
+import java.util.HashMap;
 import java.util.List;
 import java.util.Map;
 import java.util.Set;
@@ -110,17 +111,35 @@ public class FontListParser {
             long lastModifiedDate,
             int configVersion
     ) throws IOException, XmlPullParserException {
-        FontCustomizationParser.Result oemCustomization;
+        final List<String> customizationXmlPaths = new ArrayList<>();
         if (oemCustomizationXmlPath != null) {
-            try (InputStream is = new FileInputStream(oemCustomizationXmlPath)) {
-                oemCustomization = FontCustomizationParser.parse(is, productFontDir,
-                        updatableFontMap);
+            customizationXmlPaths.add(oemCustomizationXmlPath);
+        }
+        return parseWithCustomizations(fontsXmlPath, systemFontDir, customizationXmlPaths,
+                productFontDir, updatableFontMap, lastModifiedDate, configVersion);
+    }
+
+    /**
+     * Parses system font config XMLs with multiple OEM customization layers.
+     */
+    public static FontConfig parseWithCustomizations(
+            @NonNull String fontsXmlPath,
+            @NonNull String systemFontDir,
+            @NonNull List<String> customizationXmlPaths,
+            @Nullable String productFontDir,
+            @Nullable Map<String, File> updatableFontMap,
+            long lastModifiedDate,
+            int configVersion
+    ) throws IOException, XmlPullParserException {
+        FontCustomizationParser.Result oemCustomization = new FontCustomizationParser.Result();
+        for (String customizationXmlPath : customizationXmlPaths) {
+            try (InputStream is = new FileInputStream(customizationXmlPath)) {
+                oemCustomization = mergeCustomizationResults(
+                        oemCustomization,
+                        FontCustomizationParser.parse(is, productFontDir, updatableFontMap));
             } catch (IOException e) {
-                // OEM customization may not exists. Ignoring
-                oemCustomization = new FontCustomizationParser.Result();
+                // OEM customization may not exist. Ignoring.
             }
-        } else {
-            oemCustomization = new FontCustomizationParser.Result();
         }
 
         try (InputStream is = new FileInputStream(fontsXmlPath)) {
@@ -132,6 +151,23 @@ public class FontListParser {
         }
     }
 
+    private static FontCustomizationParser.Result mergeCustomizationResults(
+            @NonNull FontCustomizationParser.Result base,
+            @NonNull FontCustomizationParser.Result extra) {
+        final Map<String, NamedFamilyList> namedFamilies =
+                new HashMap<>(base.getAdditionalNamedFamilies());
+        namedFamilies.putAll(extra.getAdditionalNamedFamilies());
+
+        final List<FontConfig.Customization.LocaleFallback> localeFallbacks =
+                new ArrayList<>(base.getLocaleFamilyCustomizations());
+        localeFallbacks.addAll(extra.getLocaleFamilyCustomizations());
+
+        final List<FontConfig.Alias> aliases = new ArrayList<>(base.getAdditionalAliases());
+        aliases.addAll(extra.getAdditionalAliases());
+
+        return new FontCustomizationParser.Result(namedFamilies, localeFallbacks, aliases);
+    }
+
     /**
      * Parses the familyset tag in font.xml
      * @param parser a XML pull parser
diff --git a/graphics/java/android/graphics/fonts/SystemFonts.java b/graphics/java/android/graphics/fonts/SystemFonts.java
index 399345abd8ab..1a583c285e4d 100644
--- a/graphics/java/android/graphics/fonts/SystemFonts.java
+++ b/graphics/java/android/graphics/fonts/SystemFonts.java
@@ -25,6 +25,7 @@ import android.annotation.Nullable;
 import android.graphics.FontListParser;
 import android.graphics.Typeface;
 import android.os.LocaleList;
+import android.os.SystemProperties;
 import android.ravenwood.annotation.RavenwoodReplace;
 import android.text.FontConfig;
 import android.util.ArrayMap;
@@ -63,6 +64,19 @@ public final class SystemFonts {
     /** @hide */
     public static final String SYSTEM_FONT_DIR = getSystemFontDir();
     private static final String OEM_XML = "/product/etc/fonts_customization.xml";
+    private static final String OEM_EMOJI_XML_IOS = "/product/etc/fonts_customization_emoji_ios.xml";
+    private static final String OEM_EMOJI_XML_SAMSUNG =
+            "/product/etc/fonts_customization_emoji_samsung.xml";
+    private static final String OEM_EMOJI_XML_SWIFTUI =
+        "/product/etc/fonts_customization_emoji_swiftui.xml";
+    private static final String OEM_EMOJI_XML_FACEBOOK =
+        "/product/etc/fonts_customization_emoji_facebook.xml";
+    private static final String PROP_EMOJI_STYLE = "persist.sys.voltage_emoji_style";
+    private static final String EMOJI_STYLE_ANDROID = "android";
+    private static final String EMOJI_STYLE_IOS = "ios";
+    private static final String EMOJI_STYLE_SAMSUNG = "samsung";
+    private static final String EMOJI_STYLE_SWIFTUI = "swiftui";
+    private static final String EMOJI_STYLE_FACEBOOK = "facebook";
     /** @hide */
     public static final String OEM_FONT_DIR = "/product/fonts/";
 
@@ -352,8 +366,9 @@ public final class SystemFonts {
             long lastModifiedDate,
             int configVersion
     ) {
-        return getSystemFontConfigInternal(FONTS_XML, SYSTEM_FONT_DIR, OEM_XML, OEM_FONT_DIR,
-                updatableFontMap, lastModifiedDate, configVersion);
+        return getSystemFontConfigInternal(FONTS_XML, SYSTEM_FONT_DIR, OEM_XML,
+                getEmojiCustomizationXml(), OEM_FONT_DIR, updatableFontMap,
+                lastModifiedDate, configVersion);
     }
 
     /**
@@ -368,8 +383,9 @@ public final class SystemFonts {
             long lastModifiedDate,
             int configVersion
     ) {
-        return getSystemFontConfigInternal(fontsXml, SYSTEM_FONT_DIR, OEM_XML, OEM_FONT_DIR,
-                updatableFontMap, lastModifiedDate, configVersion);
+        return getSystemFontConfigInternal(fontsXml, SYSTEM_FONT_DIR, OEM_XML,
+                getEmojiCustomizationXml(), OEM_FONT_DIR, updatableFontMap,
+                lastModifiedDate, configVersion);
     }
 
     /**
@@ -377,22 +393,23 @@ public final class SystemFonts {
      * @hide
      */
     public static @NonNull FontConfig getSystemPreinstalledFontConfig() {
-        return getSystemFontConfigInternal(FONTS_XML, SYSTEM_FONT_DIR, OEM_XML, OEM_FONT_DIR, null,
-                0, 0);
+        return getSystemFontConfigInternal(FONTS_XML, SYSTEM_FONT_DIR, OEM_XML,
+                getEmojiCustomizationXml(), OEM_FONT_DIR, null, 0, 0);
     }
 
     /**
      * @hide
      */
     public static @NonNull FontConfig getSystemPreinstalledFontConfigFromLegacyXml() {
-        return getSystemFontConfigInternal(LEGACY_FONTS_XML, SYSTEM_FONT_DIR, OEM_XML, OEM_FONT_DIR,
-                null, 0, 0);
+        return getSystemFontConfigInternal(LEGACY_FONTS_XML, SYSTEM_FONT_DIR, OEM_XML,
+                getEmojiCustomizationXml(), OEM_FONT_DIR, null, 0, 0);
     }
 
     /* package */ static @NonNull FontConfig getSystemFontConfigInternal(
             @NonNull String fontsXml,
             @NonNull String systemFontDir,
             @Nullable String oemXml,
+            @Nullable String emojiXml,
             @Nullable String productFontDir,
             @Nullable Map<String, File> updatableFontMap,
             long lastModifiedDate,
@@ -400,8 +417,15 @@ public final class SystemFonts {
     ) {
         try {
             Log.i(TAG, "Loading font config from " + fontsXml);
-            return FontListParser.parse(fontsXml, systemFontDir, oemXml, productFontDir,
-                                                updatableFontMap, lastModifiedDate, configVersion);
+            final List<String> customizationXmls = new ArrayList<>();
+            if (oemXml != null) {
+                customizationXmls.add(oemXml);
+            }
+            if (emojiXml != null) {
+                customizationXmls.add(emojiXml);
+            }
+            return FontListParser.parseWithCustomizations(fontsXml, systemFontDir, customizationXmls,
+                    productFontDir, updatableFontMap, lastModifiedDate, configVersion);
         } catch (IOException e) {
             Log.e(TAG, "Failed to open/read system font configurations.", e);
             return new FontConfig(Collections.emptyList(), Collections.emptyList(),
@@ -413,6 +437,26 @@ public final class SystemFonts {
         }
     }
 
+    private static @Nullable String getEmojiCustomizationXml() {
+        final String style = SystemProperties.get(PROP_EMOJI_STYLE, EMOJI_STYLE_ANDROID);
+        if (EMOJI_STYLE_SAMSUNG.equals(style)) {
+            return OEM_EMOJI_XML_SAMSUNG;
+        }
+        if (EMOJI_STYLE_IOS.equals(style)) {
+            return OEM_EMOJI_XML_IOS;
+        }
+        if (EMOJI_STYLE_SWIFTUI.equals(style)) {
+            return OEM_EMOJI_XML_SWIFTUI;
+        }
+        if (EMOJI_STYLE_FACEBOOK.equals(style)) {
+            return OEM_EMOJI_XML_FACEBOOK;
+        }
+        if (EMOJI_STYLE_ANDROID.equals(style)) {
+            return null;
+        }
+        return null;
+    }
+
     /**
      * Build the system fallback from FontConfig.
      * @hide
EMOJI_FRAMEWORKS_BASE_PATCH
cat > "$bundle/patches/powerhub.patch" <<'EMOJI_POWERHUB_PATCH'
diff --git a/res/values/powerhub_arrays.xml b/res/values/powerhub_arrays.xml
index ac45b00..5d49773 100644
--- a/res/values/powerhub_arrays.xml
+++ b/res/values/powerhub_arrays.xml
@@ -417,4 +417,19 @@
         <item>1</item>
     </string-array>
 
+    <string-array name="emoji_style_entries">
+        <item>Stock</item>
+        <item>iOS</item>
+        <item>Samsung</item>
+        <item>SwiftUI</item>
+        <item>Facebook</item>
+    </string-array>
+
+    <string-array name="emoji_style_values" translatable="false">
+        <item>android</item>
+        <item>ios</item>
+        <item>samsung</item>
+        <item>swiftui</item>
+        <item>facebook</item>
+    </string-array>
 </resources>
diff --git a/res/values/powerhub_strings.xml b/res/values/powerhub_strings.xml
index 59ad075..61c8b33 100644
--- a/res/values/powerhub_strings.xml
+++ b/res/values/powerhub_strings.xml
@@ -838,4 +838,9 @@
      <string name="nirvana_time_limit_dialog_title">Daily limit reached</string>
      <string name="nirvana_time_limit_dialog_message">You\'ve reached your daily limit for %1$s. It will be available again tomorrow.</string>
 
+    <string name="emoji_style_title">Emoji style</string>
+    <string name="emoji_style_reboot_title">Restart required</string>
+    <string name="emoji_style_reboot_message">Restart your device to apply the selected emoji style. Text fonts are unchanged.</string>
+    <string name="emoji_style_restart_now">Restart now</string>
+    <string name="emoji_style_restart_later">Later</string>
 </resources>
diff --git a/res/xml/monet_settings.xml b/res/xml/monet_settings.xml
index ea1140e..c34d919 100644
--- a/res/xml/monet_settings.xml
+++ b/res/xml/monet_settings.xml
@@ -47,4 +47,13 @@
         android:icon="@drawable/ic_powerhub_qsstyle_expressive"
         android:fragment="com.power.hub.fragments.QuickSettingsStyle" />
 
+    <ListPreference
+        android:key="emoji_style"
+        android:title="@string/emoji_style_title"
+        android:summary="%s"
+        android:entries="@array/emoji_style_entries"
+        android:entryValues="@array/emoji_style_values"
+        android:defaultValue="android"
+        android:persistent="false" />
+
 </PreferenceScreen>
diff --git a/src/com/power/hub/fragments/MonetSettings.java b/src/com/power/hub/fragments/MonetSettings.java
index 8767ad7..d65af71 100644
--- a/src/com/power/hub/fragments/MonetSettings.java
+++ b/src/com/power/hub/fragments/MonetSettings.java
@@ -15,7 +15,12 @@
  */
 package com.power.hub.fragments;
 
+import android.app.AlertDialog;
 import android.os.Bundle;
+import android.os.PowerManager;
+import android.os.SystemProperties;
+
+import androidx.preference.ListPreference;
 
 import com.android.internal.logging.nano.MetricsProto;
 import com.android.settings.R;
@@ -28,6 +33,30 @@ public class MonetSettings extends DashboardFragment {
 
     public static final String TAG = "MonetSettings";
 
+    private static final String PROP_EMOJI_STYLE = "persist.sys.voltage_emoji_style";
+
+    @Override
+    public void onCreate(Bundle savedInstanceState) {
+        super.onCreate(savedInstanceState);
+        ListPreference emojiStyle = findPreference("emoji_style");
+        String style = SystemProperties.get(PROP_EMOJI_STYLE, "android");
+        emojiStyle.setValue(emojiStyle.findIndexOfValue(style) >= 0 ? style : "android");
+        emojiStyle.setOnPreferenceChangeListener((preference, newValue) -> {
+            if (newValue.equals(emojiStyle.getValue())) {
+                return true;
+            }
+            SystemProperties.set(PROP_EMOJI_STYLE, (String) newValue);
+            new AlertDialog.Builder(requireContext())
+                    .setTitle(R.string.emoji_style_reboot_title)
+                    .setMessage(R.string.emoji_style_reboot_message)
+                    .setPositiveButton(R.string.emoji_style_restart_now, (dialog, which) ->
+                            requireContext().getSystemService(PowerManager.class).reboot(null))
+                    .setNegativeButton(R.string.emoji_style_restart_later, null)
+                    .show();
+            return true;
+        });
+    }
+
     @Override
     public void onViewCreated(android.view.View view, Bundle savedInstanceState) {
         super.onViewCreated(view, savedInstanceState);
EMOJI_POWERHUB_PATCH
cat > "$bundle/patches/vendor-voltage.patch" <<'EMOJI_VENDOR_VOLTAGE_PATCH'
diff --git a/fonts/emoji/Android.bp b/fonts/emoji/Android.bp
new file mode 100644
index 00000000..bf77a3e8
--- /dev/null
+++ b/fonts/emoji/Android.bp
@@ -0,0 +1,53 @@
+// SPDX-License-Identifier: Apache-2.0
+
+prebuilt_font {
+    name: "IosEmoji.ttf",
+    src: "IosEmoji.ttf",
+    product_specific: true,
+}
+
+prebuilt_font {
+    name: "SamsungColorEmoji.ttf",
+    src: "SamsungColorEmoji.ttf",
+    product_specific: true,
+}
+
+prebuilt_font {
+    name: "SwiftUIEmoji.ttf",
+    src: "SwiftUIEmoji.ttf",
+    product_specific: true,
+}
+
+prebuilt_font {
+    name: "FacebookEmoji.ttf",
+    src: "FacebookEmoji.ttf",
+    product_specific: true,
+}
+
+prebuilt_etc {
+    name: "fonts_customization_emoji_ios.xml",
+    src: "fonts_customization_emoji_ios.xml",
+    product_specific: true,
+    required: ["IosEmoji.ttf"],
+}
+
+prebuilt_etc {
+    name: "fonts_customization_emoji_samsung.xml",
+    src: "fonts_customization_emoji_samsung.xml",
+    product_specific: true,
+    required: ["SamsungColorEmoji.ttf"],
+}
+
+prebuilt_etc {
+    name: "fonts_customization_emoji_swiftui.xml",
+    src: "fonts_customization_emoji_swiftui.xml",
+    product_specific: true,
+    required: ["SwiftUIEmoji.ttf"],
+}
+
+prebuilt_etc {
+    name: "fonts_customization_emoji_facebook.xml",
+    src: "fonts_customization_emoji_facebook.xml",
+    product_specific: true,
+    required: ["FacebookEmoji.ttf"],
+}
diff --git a/fonts/emoji/fonts_customization_emoji_facebook.xml b/fonts/emoji/fonts_customization_emoji_facebook.xml
new file mode 100644
index 00000000..b3276618
--- /dev/null
+++ b/fonts/emoji/fonts_customization_emoji_facebook.xml
@@ -0,0 +1,6 @@
+<?xml version="1.0" encoding="utf-8"?>
+<fonts-modification version="1">
+    <family customizationType="new-locale-family" operation="prepend" lang="und-Zsye">
+        <font weight="400" style="normal">FacebookEmoji.ttf</font>
+    </family>
+</fonts-modification>
diff --git a/fonts/emoji/fonts_customization_emoji_ios.xml b/fonts/emoji/fonts_customization_emoji_ios.xml
new file mode 100644
index 00000000..eb4db308
--- /dev/null
+++ b/fonts/emoji/fonts_customization_emoji_ios.xml
@@ -0,0 +1,6 @@
+<?xml version="1.0" encoding="utf-8"?>
+<fonts-modification version="1">
+    <family customizationType="new-locale-family" operation="prepend" lang="und-Zsye">
+        <font weight="400" style="normal">IosEmoji.ttf</font>
+    </family>
+</fonts-modification>
diff --git a/fonts/emoji/fonts_customization_emoji_samsung.xml b/fonts/emoji/fonts_customization_emoji_samsung.xml
new file mode 100644
index 00000000..7316cd68
--- /dev/null
+++ b/fonts/emoji/fonts_customization_emoji_samsung.xml
@@ -0,0 +1,6 @@
+<?xml version="1.0" encoding="utf-8"?>
+<fonts-modification version="1">
+    <family customizationType="new-locale-family" operation="prepend" lang="und-Zsye">
+        <font weight="400" style="normal">SamsungColorEmoji.ttf</font>
+    </family>
+</fonts-modification>
diff --git a/fonts/emoji/fonts_customization_emoji_swiftui.xml b/fonts/emoji/fonts_customization_emoji_swiftui.xml
new file mode 100644
index 00000000..20b853fb
--- /dev/null
+++ b/fonts/emoji/fonts_customization_emoji_swiftui.xml
@@ -0,0 +1,6 @@
+<?xml version="1.0" encoding="utf-8"?>
+<fonts-modification version="1">
+    <family customizationType="new-locale-family" operation="prepend" lang="und-Zsye">
+        <font weight="400" style="normal">SwiftUIEmoji.ttf</font>
+    </family>
+</fonts-modification>
diff --git a/fonts/fonts.mk b/fonts/fonts.mk
index 5943f297..4e67e23e 100644
--- a/fonts/fonts.mk
+++ b/fonts/fonts.mk
@@ -20,7 +20,11 @@ include vendor/voltage/fonts/font_files.mk
 
 # Register custom fonts
 PRODUCT_PACKAGES += \
-    fonts_customization.xml
+    fonts_customization.xml \
+    fonts_customization_emoji_ios.xml \
+    fonts_customization_emoji_samsung.xml \
+    fonts_customization_emoji_swiftui.xml \
+    fonts_customization_emoji_facebook.xml
 
 # Overlays for UI font styles
 PRODUCT_PACKAGES += \
EMOJI_VENDOR_VOLTAGE_PATCH
cat > "$bundle/fonts/SHA256SUMS" <<'EMOJI_FONT_HASHES'
b1be92fc4ae3485337ad1cb2073010e3cbee1c8e6fe8a315728429bbd5c88db8  FacebookEmoji.ttf
f06ab19cd58f6c42ee7e367205e54dd7931c1344b641b977a415a279cf11319f  IosEmoji.ttf
7ba59f7494b314155b684df75469bb64c20e3e52d9addc09d1a0904e5b6b7e74  SamsungColorEmoji.ttf
afeae2411705772be83ed17ff71bf5de7cd11b5e44e0cfde0d8268a4ca648aac  SwiftUIEmoji.ttf
EMOJI_FONT_HASHES

repos=(frameworks/base packages/apps/Powerhub vendor/voltage)
patches=(frameworks-base.patch powerhub.patch vendor-voltage.patch)
fonts=(IosEmoji.ttf SamsungColorEmoji.ttf SwiftUIEmoji.ttf FacebookEmoji.ttf)
for i in "${!repos[@]}"; do
    [[ -e "$root/${repos[i]}/.git" ]] || fail "Missing repository: ${repos[i]}"
    [[ -f "$bundle/patches/${patches[i]}" ]] || fail "Missing patch: ${patches[i]}"
done

# Reverse checks recognize our existing edits, even when they are uncommitted.
applied=0
for i in "${!repos[@]}"; do
    if git -C "$root/${repos[i]}" apply --reverse --check "$bundle/patches/${patches[i]}" 2>/dev/null; then
        applied=$((applied + 1))
    fi
done
if (( applied == 3 )); then
    (cd -- "$root/vendor/voltage/fonts/emoji" && sha256sum --check --strict "$bundle/fonts/SHA256SUMS") || fail "Existing emoji font assets differ from this bundle"
    echo "Emoji selection is already applied; nothing changed."
    exit 0
fi
(( applied == 0 )) || fail "Bundle is only partly applied. Review the three repository diffs before retrying."

if [[ -e "$root/vendor/voltage/fonts/emoji/LunarisIosEmoji.ttf" ]] ||
    git -C "$root/frameworks/base" grep -q 'persist.sys.ax_emoji_style' -- graphics/java/android/graphics/fonts/SystemFonts.java ||
    git -C "$root/packages/apps/Powerhub" grep -q 'persist.sys.ax_emoji_style' -- src/com/power/hub/fragments/MonetSettings.java; then
    fail "The older emoji implementation is present. Use a fresh upstream checkout; this script does not remove existing changes."
fi

# Complete every compatibility and cleanliness check before modifying sources.
for i in "${!repos[@]}"; do
    repo="$root/${repos[i]}"
    [[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || fail "${repos[i]} has local changes. Commit or preserve them before applying."
    git -C "$repo" apply --check "$bundle/patches/${patches[i]}" || fail "Patch incompatible with ${repos[i]}. Refresh the patch for this upstream revision; no changes applied."
done
for font in "${fonts[@]}"; do
    [[ ! -e "$root/vendor/voltage/fonts/emoji/$font" ]] || fail "Font already exists: $font; no changes applied."
done

if (( check_only )); then
    echo 'Emoji selection: compatible; no downloads or source changes.'
    exit 0
fi

# Downloads are isolated in the temporary directory. Failure leaves sources alone.
upstream="https://raw.githubusercontent.com/Lunaris-AOSP/vendor_extras/dbf2108a19bdb03a48ed28c188287cffb650f51c/product/fonts"
for font in "${fonts[@]}"; do
    remote="$font"
    [[ "$font" != IosEmoji.ttf ]] || remote="LunarisIosEmoji.ttf"
    curl --fail --location --silent --show-error --connect-timeout 15 --max-time 300 --retry 2 \
        "$upstream/$remote" --output "$bundle/fonts/$font" || fail "Font download failed: $font; no source changes applied."
done
(cd -- "$bundle/fonts" && sha256sum --check --strict SHA256SUMS) || fail "Downloaded font checksum verification failed; no source changes applied."

for i in "${!repos[@]}"; do
    git -C "$root/${repos[i]}" apply "$bundle/patches/${patches[i]}"
done
for font in "${fonts[@]}"; do
    cp -- "$bundle/fonts/$font" "$root/vendor/voltage/fonts/emoji/$font"
done

echo "Applied emoji selection. No commits or builds were created. Review with:"
for repo in "${repos[@]}"; do
    printf '  git -C %q diff\n' "$root/$repo"
    printf '  git -C %q status --short\n' "$root/$repo"
done
