# Emoji style selection

Powerhub → Themes → Emoji style offers Stock, iOS, Samsung, SwiftUI, and
Facebook. Stock is the default. Choosing a style saves it immediately and asks
whether to restart now or later. The emoji change takes effect after a full
device restart; restarting SystemUI alone does not reload every app's fonts.

This is a port of Lunaris's emoji selection, not its text font picker. It does
not install a service, download fonts at runtime, or modify the Noto font files.
The selection applies to the whole device. Apps that bundle their own emoji
images or fonts can retain their own appearance.

## How it works

The current patch script writes `persist.sys.voltage_emoji_style`. The preference
reads this property directly rather than maintaining a second saved value.
Settings already has the system identity and reboot permission; the existing
`persist.sys.*` SELinux property context permits its writes.

`SystemFonts` reads the property when loading fonts and selects a customization
XML from `/product/etc`. `FontListParser` merges that XML with the existing
`/product/etc/fonts_customization.xml`, preserving VoltageOS's named text font
families, aliases, and locale customizations. The selected XML prepends one
`und-Zsye` emoji family, with its font in `/product/fonts`. Stock Noto remains
available for characters the alternate font does not cover.

| Choice | Property value | Font | Customization XML |
|---|---|---|---|
| Stock | `android` | Existing Noto fonts | None added |
| iOS | `ios` | `IosEmoji.ttf` | `fonts_customization_emoji_ios.xml` |
| Samsung | `samsung` | `SamsungColorEmoji.ttf` | `fonts_customization_emoji_samsung.xml` |
| SwiftUI | `swiftui` | `SwiftUIEmoji.ttf` | `fonts_customization_emoji_swiftui.xml` |
| Facebook | `facebook` | `FacebookEmoji.ttf` | `fonts_customization_emoji_facebook.xml` |

Unset or unknown property values use Stock. Missing customization XML files are
ignored, as in Lunaris. Malformed XML still follows the existing framework
error handling, so validate replacement assets before shipping them.

## Repositories and maintenance

The patch script applies changes to these three repositories; it does not
create feature branches or commits:

- `frameworks/base`: font configuration selection and merging, plus a regression
  test covering text fonts, aliases, emoji priority, and missing optional XML.
- `packages/apps/Powerhub`: preference, choices, and restart dialog on the existing
  Themes screen. Powerhub is compiled into Settings by its existing build rules.
- `vendor/voltage`: four font assets and XML files under `fonts/emoji`, their
  product-specific build modules, and inclusion from `fonts/fonts.mk`.

Apply the three embedded patches together. No device-tree, Settings-repository, or
`external/noto-fonts` changes are required.

The framework port has two small compatibility adjustments: the list-based
parser entry point is called `parseWithCustomizations`, avoiding ambiguity in
existing calls that pass `null`; unknown style values fall back to Stock.
Powerhub uses a normal non-persistent list preference because the property is
already the source of truth.

To update an emoji pack, replace its font/XML pair and update the source revision
and checksum below. Its XML filename, font filename, framework mapping, and
Powerhub entry value must continue to agree. Keep the stock Noto files intact.

## Upstream sources

- [Framework selection and merging, 18245c13bd6f](https://github.com/Lunaris-AOSP/frameworks_base/commit/18245c13bd6f52c2228a8f711d109ee557127084)
- [Framework SwiftUI and Facebook choices, 3c8e13e75578](https://github.com/Lunaris-AOSP/frameworks_base/commit/3c8e13e7557843dcb1bc98d168889618566b702d)
- [Picker and restart behavior, f8116345e5b1](https://github.com/Lunaris-AOSP/packages_apps_Singularity/commit/f8116345e5b169ad1beff5c5368fbbad12804c28)
- [Picker SwiftUI and Facebook choices, 3cea0953e3d0](https://github.com/Lunaris-AOSP/packages_apps_Singularity/commit/3cea0953e3d08ec55e3a6d0128bbb5f27b786cca)
- [Font and XML assets, dbf2108a19bd](https://github.com/Lunaris-AOSP/vendor_extras/tree/dbf2108a19bdb03a48ed28c188287cffb650f51c/product)

The font/XML assets are copied unchanged. Code SPDX headers do not assign a
license to the upstream font binaries.

Font SHA-256 checksums:

```text
f06ab19cd58f6c42ee7e367205e54dd7931c1344b641b977a415a279cf11319f  IosEmoji.ttf
7ba59f7494b314155b684df75469bb64c20e3e52d9addc09d1a0904e5b6b7e74  SamsungColorEmoji.ttf
afeae2411705772be83ed17ff71bf5de7cd11b5e44e0cfde0d8268a4ca648aac  SwiftUIEmoji.ttf
b1be92fc4ae3485337ad1cb2073010e3cbee1c8e6fe8a315728429bbd5c88db8  FacebookEmoji.ttf
```

## Validation

After selecting the normal lunch target, build the affected modules:

```sh
m Settings framework-minus-apex \
    fonts_customization_emoji_ios.xml fonts_customization_emoji_samsung.xml \
    fonts_customization_emoji_swiftui.xml fonts_customization_emoji_facebook.xml
atest FrameworksCoreTests:android.graphics.TypefaceSystemFallbackTest
```

On a flashed build, verify Stock on a fresh installation; select each alternate
style and restart; reopen Powerhub to verify persistence; then switch back to
Stock. Check flags, skin tones, ZWJ sequences, newer emoji fallback, and a
non-default text font. Verify that Later defers activation and selecting the
same choice does not ask for another restart. Test with SELinux enforcing.

## Offline compatibility check

Run `bash rom-tools/scripts/features/apply-emoji-selection.sh --check .` before
applying. This checks patch compatibility without downloads or source changes.
The installer requires Powerhub and vendor/voltage; other settings/vendor layouts
need a separate feature adaptation.
