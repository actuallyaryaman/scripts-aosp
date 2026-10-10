# Telegram build updates

This wrapper works with the shell functions from `build/envsetup.sh`, including
`m` and `brunch`. It sends one status message per build and updates it
about every ten seconds with elapsed time and the latest progress. When the build
finishes, that same message becomes a compressed log attachment with the final
result in its caption. Successful builds can upload through rclone and send a
separate “Build uploaded” text after all transfers succeed. It does not use
`rom-tools/scripts/build/build.sh` or change the ROM
build scripts.

## Connect a bot

1. Open [BotFather](https://t.me/BotFather) in Telegram. Send `/newbot` and follow
   the prompts, or use a bot you already created for these notifications.
2. From the ROM root, run:

   ```sh
   python3 rom-tools/scripts/telegram/telegram-notify.py setup
   ```

3. Enter the token at the hidden prompt. Open the bot, send `/start`, and follow
   the terminal prompt. Setup discovers your private chat and sends a test
   notification.

Setup saves `.telegram-build.json` with file permissions `600`. Keep this file
local; do not share or commit it. The token is not passed to build commands or
printed in the terminal. You can change `update_interval_seconds` in this file
(default 10, minimum 5). Progress edits the same message instead of sending a new
notification for each update. Telegram rate limits and network delays can slow
updates; the notifier respects Telegram's retry delay. The bot needs no separate
hosting or running daemon.

## Build normally through the wrapper

```sh
source build/envsetup.sh
source rom-tools/scripts/telegram/telegram-build.sh

# Either lunch first:
lunch voltage_aston-cp2a-userdebug
tgbuild m bacon

# Or use brunch:
tgbuild brunch aston userdebug
```

`tgbuild` executes exactly the command you pass it, preserves its exit code, and
shows the build output in your terminal. Commands run without `tgbuild` do not
send updates. All Telegram requests run in the background; the build never waits
for a connection, status update, or log upload. Missing or invalid bot config also
does not prevent the build from running. Ctrl+C interrupts the build, stops the
progress notifier, and returns exit code 130. Final delivery runs separately in
the background, marking the same message interrupted and attaching the compressed
partial log when Telegram is reachable.

Logs are saved under `build-logs/` in the ROM root. The full `.log` stays local;
the finished `.log.gz` replaces the existing Telegram status message, without
sending a second message. Notification diagnostics are saved beside each build log
as `.log.telegram.log`. Delivery failures do not change the build's exit code;
failed final delivery leaves the logs local. Telegram's standard Bot API
allows document uploads up to 50 MB; larger compressed logs stay local.

## Optional artifact upload

After a successful build, `tgbuild` starts `telegram-upload.py` in the background
when `ROM_UPLOAD_DESTINATION` is set.
It reads the exact ZIP path from the build's `Output File` completion line and
uploads that ZIP plus `boot.img`, `dtbo.img`, `vendor_boot.img`, `init_boot.img`,
`super_empty.img`, and `vendor.img` from the same output directory. Missing or
empty artifacts, or a missing completion line, prevent all transfers. Failed
builds and Ctrl+C do not start an upload.

Files go to `ROM_UPLOAD_DESTINATION` using your existing private rclone configuration.
Set it before calling `tgbuild`, for example `export ROM_UPLOAD_DESTINATION=remote:builds/aston/`.
When unset, uploads are skipped. Set `ROM_OTA_PREFIX` for another ROM; its default is `voltage-`.
Matching filenames are replaced; older differently named ZIPs and other files
remain. Transfers use three attempts. If a transfer fails, previously transferred
files remain, later files are not transferred, and no success text is sent.
After all seven transfers succeed, Telegram receives a separate “Build uploaded”
text with the ZIP filename and destination. Uploads proceed even if Telegram is
unreachable or its config is missing.

Progress and errors are saved beside the build log as `.log.upload.log`. Uploads
and final log delivery run independently and do not delay the build wrapper's
return or change its exit code. The upload continues after the wrapper exits;
wait for completion before starting another build that rewrites the same files.
No existing artifacts are uploaded by sourcing the wrapper.

These helpers may live inside or outside the checkout. `ROM_ROOT` selects the
checkout; otherwise use the current directory when sourcing the wrapper. No ROM build is started by setup or by sourcing the wrapper.

Official references: [BotFather setup](https://core.telegram.org/bots/tutorial),
[Bot API](https://core.telegram.org/bots/api#editmessagemedia).
