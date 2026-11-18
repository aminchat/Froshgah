"""جمع‌آوری فروشگاه‌ها از اینستاگرام با instaloader (درخواستی/on-demand).

نکته: instaloader کتابخانه‌ای غیررسمی است؛ اینستاگرام ممکن است IP دیتاسنتر
(مثل GitHub Actions) را محدود کند. برای همین همه خطاها گرفته و گزارش می‌شوند.
"""
from __future__ import annotations

import inspect
import re
import time
from typing import Iterator

from ..config import settings
from ..db import get_db
from ..extract import extract_stores

_LOADER_KWARGS = dict(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    quiet=True,
    max_connection_attempts=2,
)


def _make_loader():
    from instaloader import Instaloader

    allowed = set(inspect.signature(Instaloader.__init__).parameters)
    kwargs = {k: v for k, v in _LOADER_KWARGS.items() if k in allowed}
    loader = Instaloader(**kwargs)
    if settings.ig_username and settings.ig_password:
        try:
            loader.login(settings.ig_username, settings.ig_password)
        except Exception:  # noqa: BLE001
            # ادامه به‌صورت ناشناس؛ معمولاً هشتگ‌ها محدودتر می‌شوند
            pass
    return loader


def _take(items: Iterator, n: int) -> list:
    out = []
    for i, item in enumerate(items):
        if i >= n:
            break
        out.append(item)
    return out


def _hashtag_candidates(keyword: str) -> list[str]:
    """کلیدواژه فارسی/انگلیسی → نام‌های هشتگ ممکن (اینستاگرام جستجوی متن آزاد ندارد)."""
    cleaned = re.sub(r"[^\w\u0600-\u06FF]+", " ", keyword or "").strip().lower()
    words = [w for w in cleaned.split() if w]
    out: list[str] = []
    if cleaned:
        out.append(cleaned.replace(" ", "_"))
    out.extend(words)
    seen: set[str] = set()
    return [x for x in out if len(x) > 1 and not (x in seen or seen.add(x))]


def _posts_of(hashtag_obj, n: int) -> list:
    for name in ("get_posts_resumable", "get_top_posts", "get_posts"):
        fn = getattr(hashtag_obj, name, None)
        if fn is not None:
            try:
                return _take(fn(), n)
            except Exception:  # noqa: BLE001
                continue
    posts = getattr(hashtag_obj, "posts", None)
    return _take(posts, n) if posts is not None else []


def _profile_text(profile) -> str:
    """متن بیو + لینک بیرونی (محل اصلی شماره/آیدی فروشنده‌ها)."""
    parts = [getattr(profile, "biography", None) or "", getattr(profile, "external_url", None) or ""]
    return "\n".join(p for p in parts if p)


def _post_text(post) -> str:
    return (getattr(post, "caption", None) or getattr(post, "title", None) or "").strip()


def _iter_posts(loader, hashtag: str | None, keyword: str | None, limit: int, result: dict) -> list:
    from instaloader import Hashtag

    tags: list[str] = []
    if hashtag:
        tags = [hashtag.lstrip("#").strip()]
    else:
        tags = _hashtag_candidates(keyword or "")
        if not tags:
            result["errors"].append("کلیدواژه برای ساخت هشتگ مناسب نبود؛ از --hashtag استفاده کنید.")
            return []

    out: list = []
    per = max(1, limit // max(1, len(tags))) + 2
    for tag in tags[:6]:
        try:
            obj = Hashtag.from_name(loader.context, tag)
            got = _posts_of(obj, per)
            if not got:
                result["errors"].append(f"#{tag}: پستی برنگشت (احتمال محدودیت اینستاگرام یا هشتگ اشتباه).")
            out.extend(got)
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"#{tag}: {e}")
        if len(out) >= limit:
            break
    return out[:limit]


def collect_instagram(
    hashtag: str | None = None,
    keyword: str | None = None,
    limit: int = 30,
    with_bios: bool = False,
    delay: float | None = None,
) -> dict:
    """پست‌های هشتگ/کلیدواژه را می‌خواند و فروشگاه‌ها را استخراج و ذخیره می‌کند.

    همگام (blocking) است — داخل ربات باید در thread جداگانه صدا زده شود.
    """
    delay = settings.request_delay if delay is None else delay
    db = get_db()
    result: dict = {"posts": 0, "stores": 0, "authors": 0, "errors": [], "platform": "instagram"}
    if not hashtag and not keyword:
        result["errors"].append("hashtag یا keyword لازم است.")
        return result

    try:
        loader = _make_loader()
    except Exception as e:  # noqa: BLE001
        result["errors"].append(f"instaloader: {e}")
        return result

    authors: list[str] = []
    try:
        for post in _iter_posts(loader, hashtag, keyword, limit, result):
            try:
                caption = _post_text(post)
                owner = getattr(post, "owner_username", None) or ""
                url = getattr(post, "url", None) or ""
                for s in extract_stores(caption, source="instagram", username=owner, title=owner, url=url):
                    db.upsert(s)
                    result["stores"] += 1
                if owner and owner not in authors:
                    authors.append(owner)
                result["posts"] += 1
            except Exception as e:  # noqa: BLE001
                result["errors"].append(str(e))
            time.sleep(delay)

        if with_bios and authors:
            from instaloader import Profile

            for uname in authors[:10]:
                try:
                    profile = Profile.from_username(loader.context, uname)
                    text = _profile_text(profile)
                    if text:
                        for s in extract_stores(
                            text,
                            source="instagram",
                            username=uname,
                            title=uname,
                            url=f"https://www.instagram.com/{uname}/",
                        ):
                            db.upsert(s)
                            result["stores"] += 1
                    result["authors"] += 1
                except Exception as e:  # noqa: BLE001
                    result["errors"].append(f"biography @{uname}: {e}")
                time.sleep(delay)
    except Exception as e:  # noqa: BLE001
        result["errors"].append(str(e))

    result["errors"] = list(dict.fromkeys(result["errors"]))[:10]
    return result
