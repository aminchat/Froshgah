"""خط فرمان (CLI) پروژه فروشگاه."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .config import settings
from .db import get_db
from .ui import format_store


def _print_result(result: dict) -> None:
    label = result.get("platform", "")
    print(f"✅ اتمام ({label})")
    for key, fa in (("posts", "پست"), ("messages", "پیام"), ("stores", "رکورد ذخیره‌شده")):
        if result.get(key):
            print(f"  • {fa}: {result[key]}")
    if result.get("channels"):
        print("  • کانال‌ها: " + ", ".join("@" + c for c in result["channels"]))
    for e in result.get("errors", []):
        print(f"  ⚠️ {e}")


def _cmd_init(_args) -> int:
    db = get_db()
    print(f"✅ دیتابیس آماده است: {db.path}")
    return 0


def _cmd_login(_args) -> int:
    from .collectors.telegram import login_interactive

    msg = asyncio.run(login_interactive())
    print(f"✅ {msg}")
    return 0


def _cmd_collect(args) -> int:
    if args.platform == "ig":
        if not args.hashtag and not args.keyword:
            print("خطا: یکی از --hashtag یا --keyword لازم است.", file=sys.stderr)
            return 2
        from .collectors.instagram import collect_instagram

        print(f"⏳ جمع‌آوری اینستاگرام ({args.hashtag or args.keyword}) …")
        result = collect_instagram(
            hashtag=args.hashtag,
            keyword=args.keyword,
            limit=args.limit,
            with_bios=args.bios,
        )
        _print_result(result)
        return 0 if not result.get("errors") else 1

    from .collectors.telegram import collect_telegram

    print(f"⏳ جستجوی تلگرام برای «{args.query}» …")
    result = asyncio.run(
        collect_telegram(args.query, limit=args.limit, deep=not args.no_deep)
    )
    _print_result(result)
    return 0 if not result.get("errors") else 1


def _cmd_search(args) -> int:
    db = get_db()
    rows = db.search(args.query, limit=args.limit)
    if not rows:
        print("چیزی پیدا نشد.")
        return 0
    print(f"🔍 {len(rows)} نتیجه برای «{args.query}»:\n")
    for i, d in enumerate(rows, 1):
        print(format_store(d, i))
        print()
    return 0


def _cmd_latest(args) -> int:
    rows = get_db().latest(limit=args.limit)
    if not rows:
        print("هنوز رکوردی ذخیره نشده است.")
        return 0
    for i, d in enumerate(rows, 1):
        print(format_store(d, i))
        print()
    return 0


def _cmd_stats(_args) -> int:
    print(json.dumps(get_db().stats(), ensure_ascii=False, indent=2))
    return 0


def _cmd_bot(_args) -> int:
    from .bot import run_bot

    run_bot()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="froshgah",
        description="جمع‌آوری و جستجوی فروشگاه‌های پوشاک از اینستاگرام و تلگرام",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="ساخت دیتابیس")
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("login", help="لاگین تعاملی تلگرام (یک‌بار، در ترمینال)")
    p.set_defaults(func=_cmd_login)

    p = sub.add_parser("collect", help="جمع‌آوری اطلاعات (درخواستی)")
    psub = p.add_subparsers(dest="platform", required=True)

    pi = psub.add_parser("ig", help="اینستاگرام (instaloader)")
    pi.add_argument("--hashtag", help="هشتگ بدون # (مثلاً پوشاک_زنانه)")
    pi.add_argument("--keyword", help="کلیدواژه برای پیدا کردن هشتگ‌های مرتبط")
    pi.add_argument("--limit", type=int, default=30, help="حداکثر تعداد پست (پیش‌فرض ۳۰)")
    pi.add_argument("--bios", action="store_true", help="خواندن بیوی نویسنده پست‌ها هم")
    pi.set_defaults(func=_cmd_collect)

    pt = psub.add_parser("tg", help="تلگرام (Telethon)")
    pt.add_argument("query", help="عبارت جستجو (مثلاً: فروشگاه پوشاک)")
    pt.add_argument("--limit", type=int, default=40, help="حداکثر پیام (پیش‌فرض ۴۰)")
    pt.add_argument("--no-deep", action="store_true", help="فقط همان پیام‌ها؛ بدون خواندن اخیر کانال‌ها")
    pt.set_defaults(func=_cmd_collect)

    p = sub.add_parser("search", help="جستجو در دیتابیس")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=_cmd_search)

    p = sub.add_parser("latest", help="آخرین فروشگاه‌های ذخیره‌شده")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=_cmd_latest)

    p = sub.add_parser("stats", help="آمار دیتابیس")
    p.set_defaults(func=_cmd_stats)

    p = sub.add_parser("bot", help="اجرای ربات تلگرام")
    p.set_defaults(func=_cmd_bot)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nلغو شد.", file=sys.stderr)
        return 130
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
