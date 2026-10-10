#!/usr/bin/env python3
"""Upload the completed tgbuild package and images independently of notifications."""

from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

DESTINATION = os.environ.get("ROM_UPLOAD_DESTINATION", "").rstrip("/") + "/"
PACKAGE_PREFIX = os.environ.get("ROM_OTA_PREFIX", "voltage-")
IMAGES = ("boot.img", "dtbo.img", "vendor_boot.img", "init_boot.img",
          "super_empty.img", "vendor.img")


def main():
    if not os.environ.get("ROM_UPLOAD_DESTINATION"):
        print("Upload skipped: ROM_UPLOAD_DESTINATION is unset.")
        return
    if len(sys.argv) != 3:
        raise RuntimeError("Usage: telegram-upload.py ROM_ROOT BUILD_LOG")
    root, log = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    package = None
    # The bacon completion banner identifies the exact package, including when
    # several older ZIP names are hard links with identical timestamps.
    with log.open(errors="replace") as stream:
        for line in stream:
            line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
            match = re.search(r"Output File\s*:\s*(.+?)\s*$", line)
            if match:
                package = Path(match.group(1))
    if package is None:
        raise RuntimeError("No completed ZIP in the build's Output File line; upload skipped")
    if not package.is_absolute():
        package = root / package
    if not package.name.startswith(PACKAGE_PREFIX) or package.suffix != ".zip" or package.name.endswith("-img.zip"):
        raise RuntimeError("Completion output is not an OTA ZIP matching ROM_OTA_PREFIX; upload skipped")
    files = [package, *(package.parent / name for name in IMAGES)]
    missing = [str(path) for path in files if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError("Missing or empty artifacts; no files uploaded: " + ", ".join(missing))
    if shutil.which("rclone") is None:
        raise RuntimeError("rclone is not installed; upload skipped")
    for path in files:
        print(f"Uploading {path.name} to {DESTINATION}", flush=True)
        subprocess.run(["rclone", "copyto", str(path), DESTINATION + path.name,
                        "--retries", "3", "--stats", "30s", "--verbose"], check=True)
    print(f"Build uploaded: {package.name} → {DESTINATION}", flush=True)
    # Notification failure cannot change the successful upload result.
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().with_name("telegram-notify.py")),
                             "uploaded", package.name, DESTINATION])
    if result.returncode:
        print("Files uploaded successfully; Telegram confirmation failed", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Build upload: {exc}", file=sys.stderr)
        sys.exit(1)
