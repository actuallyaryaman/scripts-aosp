#!/usr/bin/env python3
"""Send build status and logs to a private Telegram chat using the Bot API."""

import argparse
import getpass
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(os.environ.get('ROM_ROOT', '.')).resolve()
CONFIG = Path(os.environ.get("TELEGRAM_BUILD_CONFIG", ROOT / ".telegram-build.json"))
TOKEN = ""


class RateLimited(RuntimeError):
    def __init__(self, seconds):
        self.seconds = max(1, int(seconds))
        super().__init__(f"Telegram rate limit; retry after {self.seconds} seconds")


def request(method, data=None, document=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    if document is None:
        body = json.dumps(data or {}).encode()
        content_type = "application/json"
    else:
        boundary = uuid.uuid4().hex
        fields = []
        for name, value in data.items():
            fields.append(f'--{boundary}\r\nContent-Disposition: form-data; '
                          f'name="{name}"\r\n\r\n{value}\r\n'.encode())
        fields.append(f'--{boundary}\r\nContent-Disposition: form-data; '
                      f'name="document"; filename="{document.name}"\r\n'
                      'Content-Type: application/gzip\r\n\r\n'.encode())
        fields.append(document.read_bytes())
        fields.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(fields)
        content_type = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=60 if document else 10) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            try:
                seconds = json.load(exc).get("parameters", {}).get("retry_after", 10)
            except ValueError:
                seconds = 10
            raise RateLimited(seconds) from None
        raise RuntimeError(f"Telegram returned HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Cannot reach Telegram") from None
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram request failed"))
    return result["result"]


def message(chat_id, text):
    return request("sendMessage", {"chat_id": chat_id, "text": text[:4000]})


def update_status(chat_id, log, text):
    state = log.with_suffix(".telegram-message")
    if state.exists():
        return request("editMessageText", {
            "chat_id": chat_id, "message_id": int(state.read_text()), "text": text[:4000],
        })
    result = message(chat_id, text)
    state.write_text(str(result["message_id"]))
    return result


def elapsed(started):
    seconds = max(0, int(time.time()) - int(started))
    return f"{seconds // 3600}h {(seconds // 60) % 60}m {seconds % 60}s"


def latest_output(log):
    with log.open("rb") as stream:
        stream.seek(max(0, log.stat().st_size - 16384))
        text = stream.read().decode(errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    progress = [line for line in lines if re.match(r"\[\s*\d+%", line)]
    return (progress[-1] if progress else lines[-1] if lines else "Waiting for output")[-1000:]


def setup():
    global TOKEN
    if CONFIG.exists():
        raise RuntimeError(f"Config already exists: {CONFIG}; edit it to change settings")
    TOKEN = getpass.getpass("BotFather token (hidden): ").strip()
    bot = request("getMe")
    input(f"Open https://t.me/{bot['username']}, send /start, then press Enter here: ")
    updates = request("getUpdates")
    chats = {}
    for update in updates:
        chat = update.get("message", {}).get("chat", {})
        if chat.get("type") == "private":
            chats[chat["id"]] = chat.get("first_name", "Private chat")
    if not chats:
        raise RuntimeError("No private chat found. Send /start to the bot, then run setup again")
    if len(chats) == 1:
        chat_id = next(iter(chats))
    else:
        for chat_id, name in chats.items():
            print(f"{chat_id}: {name}")
        chat_id = int(input("Your private chat ID: "))
        if chat_id not in chats:
            raise RuntimeError("Choose one of the listed private chat IDs")
    config = {"bot_token": TOKEN, "chat_id": chat_id, "update_interval_seconds": 10}
    with os.fdopen(os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
    message(chat_id, "Build notifications connected. Ready for tgbuild.")
    print(f"Saved private config: {CONFIG}")


def main():
    global TOKEN
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "check", "start", "watch", "finish", "uploaded"])
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    if args.action == "setup":
        setup()
        return
    if not CONFIG.exists():
        raise RuntimeError("Run: /usr/bin/python3 rom-tools/scripts/telegram/telegram-notify.py setup")
    config = json.loads(CONFIG.read_text())
    TOKEN = config["bot_token"].strip()
    chat_id = int(config["chat_id"])
    interval = int(config.get("update_interval_seconds", 10))
    if not TOKEN or chat_id <= 0 or interval < 5:
        raise RuntimeError("Config needs a bot token, private chat ID, and interval >= 5 seconds")
    if args.action == "check":
        return
    if args.action == "uploaded":
        message(chat_id, f"Build uploaded\n{args.args[0]}\nDestination: {args.args[1]}")
        return
    if args.action == "start":
        update_status(chat_id, Path(args.args[0]), f"Build started\nCommand: {args.args[1]}")
        return
    log, started, label = Path(args.args[0]), args.args[1], args.args[2]
    if args.action == "watch":
        while True:
            try:
                update_status(chat_id, log,
                              f"Build running: {label}\nElapsed: {elapsed(started)}\n"
                              f"Latest output: {latest_output(log)}")
            except RateLimited as exc:
                time.sleep(exc.seconds)
            except (OSError, RuntimeError) as exc:
                print(f"Telegram update skipped: {exc}", file=sys.stderr, flush=True)
            time.sleep(interval)
    else:
        status = int(args.args[3])
        outcome = "succeeded" if status == 0 else "interrupted" if status in (130, 143) else "failed"
        summary = (f"Build {outcome}\nCommand: {label}\n"
                   f"Elapsed: {elapsed(started)}\nExit code: {status}\n"
                   f"Latest output: {latest_output(log)}")
        try:
            update_status(chat_id, log, summary)
        except (OSError, RuntimeError) as exc:
            print(f"Telegram status skipped: {exc}", file=sys.stderr)
        document = log.with_suffix(".log.gz")
        with log.open("rb") as source, gzip.open(document, "wb") as target:
            shutil.copyfileobj(source, target)
        if document.stat().st_size > 50_000_000:
            raise RuntimeError(f"Compressed log exceeds Telegram's upload limit; saved at {document}")
        state = log.with_suffix(".telegram-message")
        if not state.exists():
            raise RuntimeError(f"No status message to attach the log to; saved at {document}")
        request("editMessageMedia", {
            "chat_id": chat_id,
            "message_id": int(state.read_text()),
            "media": json.dumps({"type": "document", "media": "attach://document",
                                 "caption": summary[:1024]}),
        }, document=document)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Telegram: {str(exc).replace(TOKEN, '[redacted]') if TOKEN else exc}", file=sys.stderr)
        sys.exit(1)
