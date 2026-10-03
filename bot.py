"""毎日 POST_TIMES の時刻に異名を Misskey に投稿する Bot。0:00 の枠だけは神器の銘を投稿する。

投稿枠の日時 (JST, YYYYMMDDHH) をシードにするので、同じ枠なら何度動かしても同じ文になる。
状態は STATE_DIR に記録し、再起動しても二重投稿しない。

    python bot.py             # 常駐して毎日 POST_TIMES に投稿
    python bot.py --dry-run   # 今日の各枠の投稿文を表示するだけ
    python bot.py --now       # 今すぐ 1 回投稿して終了 (記録はしない)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from elinalias import AliasGenerator

JST = timezone(timedelta(hours=9))

MISSKEY_HOST = os.environ.get("MISSKEY_HOST", "misskey.io")
MISSKEY_APIKEY = os.environ.get("MISSKEY_APIKEY", "")
POST_TIMES = os.environ.get("POST_TIMES", "00:00,06:00,12:00,18:00")  # JST, カンマ区切り
STATE_DIR = Path(os.environ.get("STATE_DIR", "/data"))
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))

LAST_POSTED = STATE_DIR / "last_posted"


def alias_of(seed: int) -> str:
    return AliasGenerator.bundled("JP", seed=seed).random_alias()


def artifact_of(seed: int) -> str:
    # 伝説/神話級装備の銘と同じ生成モード (builtin=True)
    return AliasGenerator.bundled("JP", seed=seed).random_alias(builtin=True)


def slot_seed(slot: datetime) -> int:
    return int(slot.strftime("%Y%m%d%H"))  # int32 に収まる


def note_text(slot: datetime) -> str:
    if (slot.hour, slot.minute) == (0, 0):
        return f"《{artifact_of(slot_seed(slot))}》"
    return alias_of(slot_seed(slot))


def api(endpoint: str, **params):
    req = urllib.request.Request(
        f"https://{MISSKEY_HOST}/api/{endpoint}",
        data=json.dumps({"i": MISSKEY_APIKEY, **params}).encode(),
        # 既定の Python-urllib の UA は Cloudflare に弾かれる (error 1010)
        headers={"Content-Type": "application/json", "User-Agent": "elinalias-bot/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def read_state(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return None


def write_state(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def parse_times() -> list[tuple[int, int]]:
    return sorted(tuple(map(int, t.strip().split(":"))) for t in POST_TIMES.split(",") if t.strip())


def latest_slot(now: datetime, times: list[tuple[int, int]]) -> datetime:
    """now 以前で最も新しい投稿枠。今日の枠がまだなら前日の最終枠。"""
    for day in (now, now - timedelta(days=1)):
        for hh, mm in reversed(times):
            slot = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if slot <= now:
                return slot
    raise ValueError("POST_TIMES が空です")


def post_alias(slot: datetime) -> None:
    note = api("notes/create", text=note_text(slot), visibility="public")["createdNote"]
    print(f"posted: https://{MISSKEY_HOST}/notes/{note['id']}", flush=True)


def run_forever() -> None:
    times = parse_times()
    print(f"start: host={MISSKEY_HOST} post_times={POST_TIMES} JST poll={POLL_SECONDS}s", flush=True)
    while True:
        now = datetime.now(JST)
        # 止まっていて逃した枠はまとめて投稿せず、最新の枠だけ投稿する
        slot = latest_slot(now, times)
        # ネットワーク・API エラーは次のループで再試行する
        try:
            if read_state(LAST_POSTED) != slot.isoformat():
                post_alias(slot)
                write_state(LAST_POSTED, slot.isoformat())
        except Exception as e:
            print(f"post failed: {e!r}", file=sys.stderr, flush=True)
        time.sleep(POLL_SECONDS)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="今日の各枠の投稿文を表示するだけ")
    p.add_argument("--now", action="store_true", help="今すぐ 1 回投稿して終了")
    args = p.parse_args()

    now = datetime.now(JST)
    times = parse_times()
    slot = latest_slot(now, times)
    if args.dry_run:
        for hh, mm in times:
            s = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            print(f"{hh:02d}:{mm:02d} {note_text(s)}")
        return 0
    if not MISSKEY_APIKEY:
        print("MISSKEY_APIKEY が設定されていません", file=sys.stderr)
        return 1
    if args.now:
        post_alias(slot)
        return 0
    run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
