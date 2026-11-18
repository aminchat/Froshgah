"""خط فرمان (CLI) پروژه فروشگاه."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
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


def _cmd_export(args) -> int:
    from .export import export_json, import_json

    db = get_db()
    n = import_json(db, args.seed) if args.seed else 0
    path = export_json(db, args.out)
    print(f"✅ نوشته شد: {path} ({db.stats()['total']} رکورد" + (f"، ادغام از قبل: {n}" if n else "") + ")")
    return 0


def _cmd_site(args) -> int:
    from .site import build_site

    out = build_site(get_db(), args.data, args.out)
    if args.vercel_dir:
        vout = build_site(get_db(), args.data, args.vercel_dir, public=True)
        print(f"✅ پوشه Vercel هم ساخته شد: {vout}/")
    print(f"✅ سایت ساخته شد: {out}/  (با `python -m http.server` در همان پوشه قابل دیدن است)")
    return 0


def _read_payload(args) -> dict:
    """بار رمزنگاری‌شده پنل وب را باز می‌کند (اگر داده شده باشد)."""
    from .payload import decrypt, load_payload

    token = load_payload(args.payload) if args.payload else os.getenv("FROSHGAH_PAYLOAD", "").strip()
    if not token:
        return {}
    secret = os.getenv("APP_SECRET", "").strip()
    if not secret:
        raise SystemExit("برای بازکردن --payload لازم است APP_SECRET تنظیم شود (همان کلید سرویس وب).")
    try:
        return decrypt(token, secret)
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"❌ بازکردن بار پنل وب ناموفق بود: {e}")


def _cmd_run(args) -> int:
    from .run import run_job

    payload = _read_payload(args)
    if payload:
        keys = ", ".join(sorted(k for k, v in payload.items() if v and k not in {"hashtags", "keywords", "queries"}))
        print(f"🔑 بار پنل وب باز شد: {keys or '—'}")
    print("⏳ اجرای جمع‌آوری + انتشار…")
    summary = run_job(
        instagram_tags=args.ig_tags,
        instagram_keywords=args.ig_keywords,
        telegram_queries=args.tg_queries,
        limit=args.limit,
        with_bios=not args.no_bios,
        data_file=args.data,
        site_dir=None if args.no_site else args.site,
        vercel_dir=args.vercel_dir or None,
        payload=payload,
        post_url=args.post_url,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    errs = summary["instagram"]["errors"] + summary["telegram"]["errors"]
    return 1 if errs and not summary["stores_total"] else 0


def _cmd_setup(args) -> int:
    from .setup_wizard import run_setup, status

    if args.check:
        status()
        return 0
    run_setup(use_env=args.from_env)
    return 0


def _cmd_doctor(_args) -> int:
    from .doctor import report

    print("🩺 بررسی آماده‌به‌کاری\n")
    return 0 if report() else 1


def _cmd_secret(args) -> int:
    """یک رشته تصادفی قوی می‌سازد (برای APP_SECRET و SITE_PASSWORD)."""
    import secrets

    for _ in range(max(1, args.count)):
        print(secrets.token_hex(args.bytes))
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
    pi.add_argument("--keyword", help="کلیدواژه؛ به نام هشتگ احتمالی تبدیل می‌شود (مثلاً: فروشگاه پوشاک)")
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

    p = sub.add_parser("run", help="یک اجرای کامل: جمع‌آوری + JSON + ساخت سایت (مناسب GitHub Actions)")
    p.add_argument("--ig-tags", default="", help="هشتگ‌های اینستاگرام، با کاما: پوشاک,مانتو")
    p.add_argument("--ig-keywords", default="", help="کلیدواژه‌های اینستاگرام، با کاما")
    p.add_argument("--tg-queries", default="", help="عبارت‌های جستجوی تلگرام، با کاما")
    p.add_argument("--limit", type=int, default=25, help="حداکثر پست/پیام برای هر عبارت")
    p.add_argument("--no-bios", action="store_true", help="بیوی نویسنده‌ها خوانده نشود")
    p.add_argument("--data", default="data/stores.json", help="فایل JSON داده‌ها")
    p.add_argument("--site", default="docs", help="پوشه خروجی سایت (GitHub Pages)")
    p.add_argument("--vercel-dir", default="", help="پوشه پروژه Vercel (مثلاً vercel) تا public/ آن هم ساخته شود")
    p.add_argument("--payload", default="", help="بار رمزنگاری‌شده پنل وب (متن base64 یا @فایل)")
    p.add_argument("--post-url", default="", help="اگر داده باید به سرویسی برگردد: URL کامل")
    p.add_argument("--no-site", action="store_true", help="سایت ساخته نشود")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("export", help="خروجی JSON از دیتابیس")
    p.add_argument("--out", default="data/stores.json")
    p.add_argument("--seed", default="", help="فایل JSON قبلی برای ادغام قبل از خروجی")
    p.set_defaults(func=_cmd_export)

    p = sub.add_parser("site", help="ساخت سایت ایستا از دیتابیس")
    p.add_argument("--data", default="data/stores.json")
    p.add_argument("--out", default="docs")
    p.add_argument("--vercel-dir", default="", help="پوشه پروژه Vercel تا public/ آن هم ساخته شود")
    p.set_defaults(func=_cmd_site)

    p = sub.add_parser("setup", help="پرسش و ساخت فایل .env (رمزها فقط در همین رایانه می‌مانند)")
    p.add_argument("--check", action="store_true", help="فقط وضعیت فعلی را نشان بده")
    p.add_argument("--from-env", action="store_true", help="از متغیرهای محیطی بردار، سؤال نپرس")
    p.set_defaults(func=_cmd_setup)

    p = sub.add_parser("doctor", help="بررسی آماده‌به‌کاری محیط")
    p.set_defaults(func=_cmd_doctor)

    p = sub.add_parser("secret", help="ساخت رشته تصادفی برای APP_SECRET یا SITE_PASSWORD")
    p.add_argument("--count", type=int, default=1, help="چند رشته بسازد")
    p.add_argument("--bytes", type=int, default=24, help="بایت آنتروپی هر رشته (پیش‌فرض ۲۴)")
    p.set_defaults(func=_cmd_secret)

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
