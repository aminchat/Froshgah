"""داد و ستد داده با فایل JSON (پل بین دیتابیس و مخزن گیت‌هاب)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .db import Database
from .models import Store

_TEXT_FIELDS = ("title", "username", "url", "text", "instagram", "telegram", "website", "city")


def export_json(db: Database, out: str | Path) -> Path:
    """همه رکوردها را در یک فایل JSON می‌نویسد (برای Pages و برای ادامه‌دار بودن جمع‌آوری)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = db.get_all()
    generated = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    if out.exists():
        # اگر داده‌ها تغییری نکرده‌اند، برچسب زمان را ثابت نگه می‌داریم تا دیف/کامیت الکی ساخته نشود
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(prev, dict) and prev.get("stores") == rows and prev.get("generated_at"):
                generated = prev["generated_at"]
        except (json.JSONDecodeError, OSError):
            pass
    payload = {
        "generated_at": generated,
        "count": len(rows),
        "stores": rows,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def import_json(db: Database, src: str | Path) -> int:
    """اگر فایل JSON قبلی وجود داشته باشد، رکوردهایش را در دیتابیس می‌ریزد (ادغام، نه بازنویسی)."""
    src = Path(src)
    if not src.exists():
        return 0
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    rows = payload.get("stores") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return 0
    n = 0
    for row in rows:
        if not isinstance(row, dict) or not row.get("source") or not row.get("source_key"):
            continue
        store = Store(
            source=str(row["source"]),
            source_key=str(row["source_key"]),
            title=str(row.get("title") or ""),
            username=str(row.get("username") or ""),
            url=str(row.get("url") or ""),
            text=str(row.get("text") or ""),
            phones=[str(p) for p in (row.get("phones") or []) if p],
            instagram=str(row.get("instagram") or ""),
            telegram=str(row.get("telegram") or ""),
            website=str(row.get("website") or ""),
            city=str(row.get("city") or ""),
            categories=[str(c) for c in (row.get("categories") or []) if c],
        )
        db.upsert(store)
        db.set_seen(
            store.source,
            store.source_key,
            row.get("first_seen") or "",
            row.get("last_seen") or "",
        )
        n += 1
    return n
