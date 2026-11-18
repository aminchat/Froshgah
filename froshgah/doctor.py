"""بررسی آماده‌به‌کاری محیط — `python -m froshgah doctor`."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from .config import ROOT_DIR, settings
from .setup_wizard import mask, read_env_file

OK, WARN, FAIL = "✅", "⚠️", "❌"


_ENV_TO_SETTINGS = {
    "IG_USERNAME": "ig_username",
    "IG_PASSWORD": "ig_password",
    "TG_API_ID": "tg_api_id",
    "TG_API_HASH": "tg_api_hash",
    "TG_SESSION_PATH": "tg_session_path",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_OWNER_ID": "owner_id",
    "REQUEST_DELAY": "request_delay",
}


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def check() -> list[tuple[str, str, str]]:
    """لیست (نشانه، عنوان، توضیح) — از بالا به پایین، همان‌طور که کاربر اجرا می‌کند."""
    out: list[tuple[str, str, str]] = []
    py = sys.version_info
    out.append((
        OK if py >= (3, 10) else FAIL,
        f"پایتون {py.major}.{py.minor}.{py.micro}",
        "نسخه ۳.۱۰ یا جدیدتر لازم است" if py < (3, 10) else "مناسب است",
    ))
    for mod, label, needed in (
        ("instaloader", "instaloader (اینستاگرام)", True),
        ("telethon", "telethon (تلگرام)", True),
        ("telegram", "python-telegram-bot (ربات)", False),
        ("dotenv", "python-dotenv", False),
    ):
        if _has_module(mod):
            out.append((OK, label, "نصب شده"))
        else:
            out.append((FAIL if needed else WARN, label, "نصب نشده — `pip install -r requirements.txt`"))

    env = read_env_file(ROOT_DIR / ".env")

    def val(key: str):
        """اول فایل .env، بعد متغیر محیطی، بعد مقدار خوانده‌شده در Settings."""
        if env.get(key):
            return env[key]
        if os.getenv(key):
            return os.environ[key]
        attr = _ENV_TO_SETTINGS.get(key)
        return getattr(settings, attr, "") if attr else ""

    ig_user, ig_pass = str(val("IG_USERNAME")), str(val("IG_PASSWORD"))
    if ig_user and ig_pass:
        out.append((OK, "اینستاگرام", f"با اکانت {ig_user} وارد می‌شود"))
    else:
        out.append((WARN, "اینستاگرام", "IG_USERNAME/IG_PASSWORD تنظیم نشده — حالت ناشناس، نتایج کمتر"))

    api_id, api_hash = int(val("TG_API_ID") or 0), str(val("TG_API_HASH"))
    session = Path(str(val("TG_SESSION_PATH") or (ROOT_DIR / "froshgah")))
    session_file = session if session.suffix == ".session" else Path(str(session) + ".session")
    if not (api_id and api_hash):
        out.append((WARN, "تلگرام", "TG_API_ID/TG_API_HASH تنظیم نشده — جمع‌آوری تلگرام رد می‌شود"))
    elif not session_file.exists():
        out.append((WARN, "تلگرام", "سشن ساخته نشده — یک‌بار `python -m froshgah login`"))
    else:
        out.append((OK, "تلگرام", f"آماده (سشن: {session_file.name})"))

    if str(val("TELEGRAM_BOT_TOKEN")):
        owner = int(val("TELEGRAM_OWNER_ID") or 0)
        out.append((
            OK if owner else WARN,
            "ربات تلگرام",
            f"توکن {mask(str(val('TELEGRAM_BOT_TOKEN')))}" + ("" if owner else " — TELEGRAM_OWNER_ID را هم بگذارید"),
        ))
    else:
        out.append((WARN, "ربات تلگرام", "اختیاری — TELEGRAM_BOT_TOKEN تنظیم نشده (سایت Pages کار می‌کند)"))

    try:
        from .db import Database

        db = Database()
        if Path(db.path).exists():
            s = db.stats()
            out.append((OK if s["total"] else WARN, "دیتابیس", f"{s['total']} رکورد در {db.path.name}"))
        else:
            out.append((WARN, "دیتابیس", f"ساخته نشده ({db.path.name}) — `python -m froshgah init`"))
    except Exception as e:  # noqa: BLE001
        out.append((FAIL, "دیتابیس", str(e)))

    data = ROOT_DIR / "data" / "stores.json"
    site = ROOT_DIR / "docs" / "index.html"
    out.append((
        OK if data.exists() else WARN,
        "داده انتشار",
        str(data.relative_to(ROOT_DIR)) if data.exists() else "data/stores.json هنوز ساخته نشده",
    ))
    out.append((
        OK if site.exists() else WARN,
        "سایت",
        "docs/ آماده انتشار است" if site.exists() else "docs/ ساخته نشده — `python -m froshgah site`",
    ))
    return out


def report(out=sys.stdout) -> bool:
    ready = True
    for mark, title, note in check():
        print(f"  {mark} {title:<22} {note}", file=out)
        if mark == FAIL:
            ready = False
    return ready
