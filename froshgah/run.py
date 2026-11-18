"""یک اجرای کامل: ادغام داده قبلی ← جمع‌آوری ← خروجی JSON ← ساخت سایت.

این همان مسیری است که GitHub Actions اجرا می‌کند (و شما هم در ترمینال).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from .config import settings
from .db import Database
from .export import export_json, import_json
from .site import build_site


def _split(value: str) -> list[str]:
    return [x.strip().lstrip("#").strip() for x in (value or "").split(",") if x.strip().lstrip("#").strip()]


def run_job(
    instagram_tags: str = "",
    instagram_keywords: str = "",
    telegram_queries: str = "",
    limit: int = 25,
    with_bios: bool = True,
    data_file: str | Path = "data/stores.json",
    site_dir: str | Path | None = "docs",
    db: Database | None = None,
) -> dict:
    """جمع‌آوری چندتایی + انتشار. هیچ خطایی باعث توقف کامل نمی‌شود."""
    started = time.time()
    db = db or Database()
    db.init()
    merged = import_json(db, data_file)

    summary: dict = {
        "merged_from_cache": merged,
        "instagram": {"tags": [], "keywords": [], "errors": []},
        "telegram": {"queries": [], "errors": []},
        "stores_total": 0,
        "duration": 0.0,
    }

    for tag in _split(instagram_tags):
        from .collectors.instagram import collect_instagram

        try:
            r = collect_instagram(hashtag=tag, limit=limit, with_bios=with_bios)
            summary["instagram"]["tags"].append({"tag": tag, "posts": r["posts"], "stores": r["stores"]})
            summary["instagram"]["errors"].extend(r["errors"])
        except Exception as e:  # noqa: BLE001
            summary["instagram"]["errors"].append(f"#{tag}: {e}")

    for kw in _split(instagram_keywords):
        from .collectors.instagram import collect_instagram

        try:
            r = collect_instagram(keyword=kw, limit=limit, with_bios=with_bios)
            summary["instagram"]["keywords"].append(
                {"keyword": kw, "posts": r["posts"], "stores": r["stores"]}
            )
            summary["instagram"]["errors"].extend(r["errors"])
        except Exception as e:  # noqa: BLE001
            summary["instagram"]["errors"].append(f"«{kw}»: {e}")

    queries = _split(telegram_queries)
    if queries:
        if not settings.tg_api_id or not settings.tg_api_hash:
            summary["telegram"]["errors"].append("TG_API_ID/TG_API_HASH تنظیم نشده — تلگرام رد شد.")
        else:
            from .collectors.telegram import collect_telegram

            for q in queries:
                try:
                    r = asyncio.run(collect_telegram(q, limit=limit))
                    summary["telegram"]["queries"].append(
                        {"query": q, "messages": r["messages"], "stores": r["stores"]}
                    )
                    summary["telegram"]["errors"].extend(r["errors"])
                except Exception as e:  # noqa: BLE001
                    summary["telegram"]["errors"].append(f"«{q}»: {e}")
    # حذف تکراری‌های خطا
    for k in ("instagram", "telegram"):
        summary[k]["errors"] = list(dict.fromkeys(summary[k]["errors"]))[:10]

    export_json(db, data_file)
    if site_dir:
        build_site(db, data_file, site_dir)
    summary["stores_total"] = db.stats()["total"]
    summary["duration"] = round(time.time() - started, 1)
    return summary
