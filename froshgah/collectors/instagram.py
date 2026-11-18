"""جمع‌آوری فروشگاه‌ها از اینستاگرام با instaloader (درخواستی/on-demand)."""
from __future__ import annotations

import time
from typing import Iterator

from ..config import settings
from ..db import get_db
from ..extract import extract_stores


def _make_loader():
    from instaloader import Instaloader

    loader = Instaloader(
        download_pictures=False,
        download_video_thumbs=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        max_connection_attempts=2,
    )
    if settings.ig_username and settings.ig_password:
        try:
            loader.login(settings.ig_username, settings.ig_password)
        except Exception:
            # ادامه به صورت ناشناس؛ ممکن است هشتگ‌ها محدود شوند
            pass
    return loader


def _take(items: Iterator, n: int) -> list:
    out = []
    for i, item in enumerate(items):
        if i >= n:
            break
        out.append(item)
    return out


def _posts_of(loader, hashtag_obj, n: int) -> list:
    posts = getattr(hashtag_obj, "posts", None)
    if posts is None and hasattr(hashtag_obj, "get_posts"):
        posts = hashtag_obj.get_posts()
    if posts is None:
        return []
    return _take(posts, n)


def _iter_posts(loader, hashtag: str | None, keyword: str | None, limit: int, result: dict) -> list:
    from instaloader import Hashtag

    if hashtag:
        tag = hashtag.lstrip("#").strip()
        try:
            obj = Hashtag.from_name(loader.context, tag)
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"هشتگ #{tag}: {e}")
            return []
        return _posts_of(loader, obj, limit)

    # جستجوی کلیدواژه → پیدا کردن هشتگ‌های مرتبط
    tags: list[str] = []
    searcher = getattr(loader.context, "search_hashtags", None)
    if searcher is None:
        result["errors"].append("این نسخه از instaloader جستجوی هشتگ ندارد؛ از --hashtag استفاده کنید.")
        return []
    try:
        for h in searcher(keyword):
            tags.append(h.name)
            if len(tags) >= 5:
                break
    except Exception as e:  # noqa: BLE001
        result["errors"].append(f"جستجوی هشتگ: {e}")
        return []
    if not tags:
        result["errors"].append(f"هشتگی برای «{keyword}» پیدا نشد.")
        return []
    out: list = []
    per = max(1, limit // len(tags)) + 2
    for t in tags:
        try:
            obj = Hashtag.from_name(loader.context, t)
            out.extend(_posts_of(loader, obj, per))
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"#{t}: {e}")
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
    """جمع‌آوری پست‌های هشتگ/کلیدواژه و استخراج فروشگاه‌ها. (همزمان — در thread جداگانه اجرا شود)"""
    delay = settings.request_delay if delay is None else delay
    db = get_db()
    result: dict = {"posts": 0, "stores": 0, "errors": [], "platform": "instagram"}
    if not hashtag and not keyword:
        result["errors"].append("hashtag یا keyword لازم است.")
        return result

    loader = _make_loader()
    authors: list[str] = []

    try:
        posts = _iter_posts(loader, hashtag, keyword, limit, result)
        for post in posts:
            try:
                caption = getattr(post, "caption", None) or ""
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
                    bio = getattr(profile, "bio", None) or ""
                    if bio:
                        for s in extract_stores(
                            bio,
                            source="instagram",
                            username=uname,
                            title=uname,
                            url=f"https://www.instagram.com/{uname}/",
                        ):
                            db.upsert(s)
                            result["stores"] += 1
                except Exception as e:  # noqa: BLE001
                    result["errors"].append(f"bio @{uname}: {e}")
                time.sleep(delay)
    except Exception as e:  # noqa: BLE001
        result["errors"].append(str(e))

    result["errors"] = result["errors"][:10]
    return result
