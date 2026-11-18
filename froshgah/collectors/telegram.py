"""جمع‌آوری فروشگاه‌ها از تلگرام با Telethon (درخواستی/on-demand)."""
from __future__ import annotations

import asyncio

from ..config import settings
from ..db import get_db
from ..extract import extract_stores


def _require_api() -> None:
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise RuntimeError("TG_API_ID و TG_API_HASH در فایل .env تنظیم نشده است.")


async def login_interactive() -> str:
    """لاگین تعاملی تلگرام (فقط در ترمینال؛ کد تأیید را می‌پرسد)."""
    from telethon import TelegramClient

    _require_api()
    client = TelegramClient(settings.tg_session_path, settings.tg_api_id, settings.tg_api_hash)
    await client.start()
    me = await client.get_me()
    await client.disconnect()
    if not me:
        return "ورود انجام شد."
    uname = f" @{me.username}" if getattr(me, "username", None) else ""
    return f"ورود موفق: {me.first_name}{uname}"


def _chat_title(chat) -> str:
    if chat is None:
        return ""
    title = getattr(chat, "title", None)
    if title:
        return str(title)
    parts = [getattr(chat, "first_name", None), getattr(chat, "last_name", None)]
    return " ".join(p for p in parts if p)


async def collect_telegram(
    query: str,
    limit: int = 40,
    deep: bool = True,
    deep_channels: int = 5,
    delay: float | None = None,
) -> dict:
    """جستجوی سراسری پیام‌ها در تلگرام و استخراج فروشگاه‌ها."""
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
    from telethon.tl.functions.messages import SearchRequest
    from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

    _require_api()
    delay = settings.request_delay if delay is None else delay
    db = get_db()
    result: dict = {"messages": 0, "stores": 0, "channels": [], "errors": [], "platform": "telegram"}

    if not query or not query.strip():
        result["errors"].append("عبارت جستجو خالی است.")
        return result

    client = TelegramClient(settings.tg_session_path, settings.tg_api_id, settings.tg_api_hash)
    try:
        await client.connect()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"اتصال به تلگرام ناموفق: {e}") from e

    try:
        if not await client.is_user_authorized():
            raise RuntimeError("جلسه تلگرام ساخته نشده؛ اول دستور `login` را در ترمینال اجرا کنید.")

        try:
            resp = await client(
                SearchRequest(
                    peer=InputPeerEmpty(),
                    q=query,
                    filter=InputMessagesFilterEmpty(),
                    offset_date=0,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=min(max(limit, 1), 100),
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )
        except FloodWaitError as e:
            raise RuntimeError(f"تلگرام محدودیت اعمال کرد؛ {e.seconds} ثانیه دیگر دوباره امتحان کنید.") from e

        entities = {}
        for c in list(getattr(resp, "chats", None) or []) + list(getattr(resp, "users", None) or []):
            entities[c.id] = c

        targets: list[tuple[str, str]] = []
        for m in getattr(resp, "messages", None) or []:
            text = getattr(m, "message", None)
            if not text:
                continue
            peer = getattr(m, "peer_id", None)
            chat = None
            if peer is not None:
                for attr in ("channel_id", "chat_id", "user_id"):
                    cid = getattr(peer, attr, None)
                    if cid is not None and cid in entities:
                        chat = entities[cid]
                        break
            username = (getattr(chat, "username", None) or "") if chat else ""
            title = _chat_title(chat)
            url = f"https://t.me/{username}/{m.id}" if username else ""
            for s in extract_stores(text, source="telegram", username=username, title=title, url=url):
                db.upsert(s)
                result["stores"] += 1
            result["messages"] += 1
            if username and username not in [t[0] for t in targets]:
                targets.append((username, title))
            await asyncio.sleep(min(delay, 1.0))

        # غنی‌سازی: چند پیام اخیر کانال‌های پیداشده
        if deep and targets:
            for username, title in targets[:deep_channels]:
                try:
                    msgs = await client.get_messages(username, limit=10)
                except FloodWaitError as e:
                    result["errors"].append(f"محدودیت تلگرام تا {e.seconds} ثانیه")
                    break
                except Exception as e:  # noqa: BLE001
                    result["errors"].append(f"t.me/{username}: {e}")
                    await asyncio.sleep(delay)
                    continue
                for m in msgs:
                    if not m or not getattr(m, "message", None):
                        continue
                    url = f"https://t.me/{username}/{m.id}"
                    for s in extract_stores(
                        m.message, source="telegram", username=username, title=title, url=url
                    ):
                        db.upsert(s)
                        result["stores"] += 1
                    result["messages"] += 1
                await asyncio.sleep(delay)
            result["channels"] = [u for u, _ in targets[:deep_channels]]
    finally:
        await client.disconnect()

    result["errors"] = result["errors"][:10]
    return result
