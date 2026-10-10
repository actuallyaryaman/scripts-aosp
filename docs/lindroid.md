# Lindroid setup

Run from the ROM root:

```bash
bash rom-tools/scripts/features/setup-lindroid.sh --help
bash rom-tools/scripts/features/setup-lindroid.sh --check .
bash rom-tools/scripts/features/setup-lindroid.sh .
```

The installer targets the existing aston device tree, sm8550 kernel, framework,
build and policy layouts. It fetches pinned Linux-on-droid dependencies when
applying; the check is offline and does not apply patches. Review the source
and `--help` for pinned revisions and exact changes. Another ROM must have
compatible patch contexts; a matching device name alone is insufficient.

`--fix-fcm` is an optional SYSVIPC workaround. Check it independently before
applying: `bash rom-tools/scripts/features/setup-lindroid.sh --fix-fcm --check .`.
The installer does not build or flash. Device qualification remains a manual step.
