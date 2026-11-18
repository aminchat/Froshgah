"""ربات تلگرام جستجوی فروشگاه‌های پوشاک."""
from __future__ import annotations

import asyncio
import html

from .config import settings
from .db import get_db
from .ui import format_store

_MAX_MSG = 3900


def _is_owner(update) -> bool:
    if not settings.owner_id:
        return False
    user = update.effective_user
    return bool(user and user.id == settings.owner_id)


def _owner_hint() -> str:
    if not settings.owner_id:
        return "⚠️ شناسه مدیر (TELEGRAM_OWNER_ID) در فایل .env تنظیم نشده است."
    return "⛔ فقط مدیر ربات می‌تواند این دستور را اجرا کند."


def _fmt_result(result: dict, label: str) -> str:
    lines = [f"✅ {label} تمام شد."]
    if result.get("posts"):
        lines.append(f"پست‌های خوانده‌شده: {result['posts']}")
    if result.get("messages"):
        lines.append(f"پیام‌های خوانده‌شده: {result['messages']}")
    if result.get("channels"):
        lines.append("کانال‌ها: " + ", ".join(f"@{c}" for c in result["channels"]))
    lines.append(f"رکوردهای ذخیره/به‌روزرسانی‌شده: {result.get('stores', 0)}")
    if result.get("errors"):
        lines.append("⚠️ خطاها:")
        lines.extend(f"• {e}" for e in result["errors"][:5])
    return "\n".join(lines)


async def cmd_start(update, _ctx) -> None:
    await update.message.reply_text(
        "سلام! 👋\n"
        "من ربات جستجوی فروشگاه‌های پوشاک از اینستاگرام و تلگرام هستم.\n\n"
        "دستورات:\n"
        "/search <عبارت> — جستجو در فروشگاه‌های ذخیره‌شده\n"
        "/latest — آخرین فروشگاه‌های اضافه‌شده\n"
        "/stats — آمار دیتابیس\n"
        "/collect_ig <هشتگ> [تعداد] — جمع‌آوری از اینستاگرام (فقط مدیر)\n"
        "/collect_tg <عبارت> — جستجوی تلگرام (فقط مدیر)\n"
        "/help — همین راهنما\n\n"
        "نکته: اول باید یک‌بار دیتابیس را با /collect_ig یا /collect_tg پر کنید."
    )


async def cmd_search(update, ctx) -> None:
    query = " ".join(ctx.args or []).strip()
    if not query:
        await update.message.reply_text(" نحوه استفاده:\n/search مانتو تهران")
        return
    db = get_db()
    rows = db.search(query, limit=10)
    if not rows:
        await update.message.reply_text(
            "🔍 چیزی پیدا نشد.\n"
            "با /collect_ig پوشاک یا /collect_tg فروشگاه پوشاک دیتابیس را پر کنید."
        )
        return
    body = "\n\n".join(format_store(d, i + 1, as_html=True) for i, d in enumerate(rows))
    head = f"🔍 {len(rows)} نتیجه برای «{html.escape(query)}»:\n\n"
    msg = head + body
    if len(msg) > _MAX_MSG:
        msg = msg[:_MAX_MSG] + "\n…"
    await update.message.reply_text(msg)


async def cmd_latest(update, _ctx) -> None:
    db = get_db()
    rows = db.latest(limit=10)
    if not rows:
        await update.message.reply_text("هنوز رکوردی ذخیره نشده است. با /collect_ig شروع کنید.")
        return
    body = "\n\n".join(format_store(d, i + 1, as_html=True) for i, d in enumerate(rows))
    msg = f"🕒 آخرین فروشگاه‌ها:\n\n{body}"
    if len(msg) > _MAX_MSG:
        msg = msg[:_MAX_MSG] + "\n…"
    await update.message.reply_text(msg)


async def cmd_stats(update, _ctx) -> None:
    s = get_db().stats()
    await update.message.reply_text(
        "📊 آمار دیتابیس:\n"
        f"• کل رکوردها: {s['total']}\n"
        f"• اینستاگرام: {s['instagram']}\n"
        f"• تلگرام: {s['telegram']}\n"
        f"• با شماره تلفن: {s['with_phone']}"
    )


async def cmd_collect_ig(update, ctx) -> None:
    if not _is_owner(update):
        await update.message.reply_text(_owner_hint())
        return
    args = list(ctx.args or [])
    if not args:
        await update.message.reply_text(" نحوه استفاده:\n/collect_ig پوشاک 30\n(تعداد اختیاری، پیش‌فرض ۳۰)")
        return
    hashtag = args[0].lstrip("#")
    limit = 30
    if len(args) > 1 and args[1].isdigit():
        limit = min(int(args[1]), 100)
    status = await update.message.reply_text(f"⏳ در حال جمع‌آوری #{hashtag} از اینستاگرام… (ممکن است چند دقیقه طول بکشد)")
    from .collectors.instagram import collect_instagram

    result = await asyncio.to_thread(
        collect_instagram, hashtag=hashtag, limit=limit, with_bios=True
    )
    try:
        await status.edit_text(_fmt_result(result, f"جمع‌آوری #{hashtag}"))
    except Exception:  # noqa: BLE001
        await update.message.reply_text(_fmt_result(result, f"جمع‌آوری #{hashtag}"))


async def cmd_collect_tg(update, ctx) -> None:
    if not _is_owner(update):
        await update.message.reply_text(_owner_hint())
        return
    query = " ".join(ctx.args or []).strip()
    if not query:
        await update.message.reply_text(" نحوه استفاده:\n/collect_tg فروشگاه پوشاک تهران")
        return
    status = await update.message.reply_text(f"⏳ در حال جستجوی تلگرام برای «{query}»…")
    from .collectors.telegram import collect_telegram

    try:
        result = await collect_telegram(query, limit=40, deep=True)
    except RuntimeError as e:
        await status.edit_text(f"❌ {e}")
        return
    try:
        await status.edit_text(_fmt_result(result, f"جستجوی تلگرام «{query}»"))
    except Exception:  # noqa: BLE001
        await update.message.reply_text(_fmt_result(result, f"جستجوی تلگرام «{query}»"))


async def cmd_error(update, _ctx) -> None:
    if update.message:
        await update.message.reply_text("❌ خطایی رخ داد. دوباره امتحان کنید یا /help بزنید.")


def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN در فایل .env تنظیم نشده است.\n"
            "از @BotFather توکن بگیرید و در .env قرار دهید."
        )
    from telegram import Update
    from telegram.ext import Application, CommandHandler

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("collect_ig", cmd_collect_ig))
    app.add_handler(CommandHandler("collect_tg", cmd_collect_tg))
    print("🤖 ربات در حال اجرا (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
