"""یک اجرای کامل: ادغام داده قبلی ← جمع‌آوری ← خروجی JSON ← ساخت سایت.

این همان مسیری است که GitHub Actions (و اسکریپت Codespaces) اجرا می‌کنند.
اگر پنل وب مقدار `payload` (بار رمزنگاری‌شده) را بفرستد، رمزهای اینستاگرام/تلگرام
از همان‌جا خوانده می‌شوند و فقط در حافظه همین پروسه می‌مانند.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from . import config
from .db import Database
from .export import export_json, import_json
from .payload import post_json
from .site import build_site


def _split(value: str) -> list[str]:
    return [x.strip().lstrip("#").strip() for x in (value or "").split(",") if x.strip().lstrip("#").strip()]


def apply_payload(payload: dict) -> dict:
    """مقادیر فرم وب را روی تنظیمات جاری می‌نشیند. برگشت: چه چیزی اعمال شد (بدون رمز)."""
    applied = {}
    if not payload:
        return applied
    values = {
        "ig_username": payload.get("ig_user", ""),
        "ig_password": payload.get("ig_pass", ""),
        "tg_api_id": payload.get("tg_api_id", ""),
        "tg_api_hash": payload.get("tg_api_hash", ""),
    }
    session = str(payload.get("tg_session", "") or "").strip()
    if session:
        # سشن تلگرام به‌صورت base64 فایل می‌آید؛ در یک پوشه موقت مخرج می‌شود
        import base64

        try:
            raw = base64.b64decode(session)
            tmp = Path(tempfile.mkdtemp(prefix="froshgah-"))
            (tmp / "froshgah.session").write_bytes(raw)
            values["tg_session_path"] = str(tmp / "froshgah")
        except Exception:  # noqa: BLE001
            values["tg_session_path"] = ""
    config.apply_overrides(**{k: v for k, v in values.items() if v})
    for key, label in (
        ("ig_user", "IG_USERNAME"),
        ("ig_pass", "IG_PASSWORD"),
        ("tg_api_id", "TG_API_ID"),
        ("tg_api_hash", "TG_API_HASH"),
        ("tg_session", "TG_SESSION"),
    ):
        if payload.get(key):
            applied[label] = "set"
    return applied


def run_job(
    instagram_tags: str = "",
    instagram_keywords: str = "",
    telegram_queries: str = "",
    limit: int = 25,
    with_bios: bool = True,
    data_file: str | Path = "data/stores.json",
    site_dir: str | Path | None = "docs",
    vercel_dir: str | Path | None = None,
    db: Database | None = None,
    payload: dict | None = None,
    post_url: str = "",
    post_token: str = "",
) -> dict:
    """جمع‌آوری چندتایی + انتشار. هیچ خطایی باعث توقف کامل نمی‌شود."""
    started = time.time()
    applied = apply_payload(payload or {})
    db = db or Database()
    db.init()
    merged = import_json(db, data_file)

    tags = _split(instagram_tags) + [str(t) for t in (payload or {}).get("hashtags", [])]
    keywords = _split(instagram_keywords) + [str(t) for t in (payload or {}).get("keywords", [])]
    queries = _split(telegram_queries) + [str(q) for q in (payload or {}).get("queries", [])]
    if (payload or {}).get("limit"):
        try:
            limit = min(max(int(payload["limit"]), 1), 100)
        except (TypeError, ValueError):
            pass
    if payload and "bios" in payload:
        with_bios = bool(payload["bios"])

    summary: dict = {
        "merged_from_cache": merged,
        "from_web_form": applied,
        "instagram": {"tags": [], "keywords": [], "errors": []},
        "telegram": {"queries": [], "errors": []},
        "stores_total": 0,
        "duration": 0.0,
    }

    for tag in [t for t in tags if t]:
        from .collectors.instagram import collect_instagram

        try:
            r = collect_instagram(hashtag=tag, limit=limit, with_bios=with_bios)
            summary["instagram"]["tags"].append({"tag": tag, "posts": r["posts"], "stores": r["stores"]})
            summary["instagram"]["errors"].extend(r["errors"])
        except Exception as e:  # noqa: BLE001
            summary["instagram"]["errors"].append(f"#{tag}: {e}")

    for kw in [k for k in keywords if k]:
        from .collectors.instagram import collect_instagram

        try:
            r = collect_instagram(keyword=kw, limit=limit, with_bios=with_bios)
            summary["instagram"]["keywords"].append(
                {"keyword": kw, "posts": r["posts"], "stores": r["stores"]}
            )
            summary["instagram"]["errors"].extend(r["errors"])
        except Exception as e:  # noqa: BLE001
            summary["instagram"]["errors"].append(f"«{kw}»: {e}")

    if queries:
        if not config.settings.tg_api_id or not config.settings.tg_api_hash:
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
    for k in ("instagram", "telegram"):
        summary[k]["errors"] = list(dict.fromkeys(summary[k]["errors"]))[:10]

    export_json(db, data_file)
    if site_dir:
        build_site(db, data_file, site_dir)
    if vercel_dir:
        build_site(db, data_file, vercel_dir, public=True)
    summary["stores_total"] = db.stats()["total"]
    summary["duration"] = round(time.time() - started, 1)

    post_url = post_url or os.getenv("POST_URL", "")
    if post_url:
        ok, detail = post_json(
            post_url,
            post_token or os.getenv("POST_TOKEN", ""),
            {
                "source": "runner",
                "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                "count": summary["stores_total"],
                "summary": summary,
                "stores": db.get_all(),
            },
        )
        summary["post"] = {"ok": ok, "detail": detail, "url": post_url}

    return summary

