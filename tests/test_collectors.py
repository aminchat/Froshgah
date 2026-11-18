"""تست‌های سبک برای جمع‌آورندها (بدون شبکه)."""
import pytest

from froshgah.collectors import instagram as ig
from froshgah.collectors import telegram as tg


def test_loader_kwargs_are_supported_by_instaloader():
    """نام پارامترهای Instaloader باید معتبر باشد (با نسخه نصبی)."""
    loader = ig._make_loader()
    assert getattr(loader, "download_pictures", False) is False
    assert getattr(loader, "save_metadata", False) is False


def test_hashtag_candidates_from_keyword():
    assert ig._hashtag_candidates("فروشگاه پوشاک") == ["فروشگاه_پوشاک", "فروشگاه", "پوشاک"]
    assert ig._hashtag_candidates("Men Wear") == ["men_wear", "men", "wear"]
    assert ig._hashtag_candidates("") == []
    assert ig._hashtag_candidates("a") == []


def test_profile_text_uses_biography_and_external_url():
    class P:
        biography = "شماره: 09121234567"
        external_url = "https://nika.example"

    assert ig._profile_text(P()) == "شماره: 09121234567\nhttps://nika.example"


def test_collect_instagram_requires_query(tmp_path, monkeypatch):
    from dataclasses import replace

    from froshgah import config
    from froshgah import db as dbmod

    fresh = replace(config.get_settings(), db_path=tmp_path / "x.db")
    monkeypatch.setattr(dbmod, "settings", fresh)
    result = ig.collect_instagram()
    assert result["stores"] == 0
    assert any("لازم است" in e for e in result["errors"])


def test_telegram_chat_title():
    class C:
        title = "فروشگاه پوشاک"

    class U:
        first_name = "علی"
        last_name = "رضایی"

    assert tg._chat_title(C()) == "فروشگاه پوشاک"
    assert tg._chat_title(U()) == "علی رضایی"
    assert tg._chat_title(None) == ""


def test_telegram_requires_api_and_query(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        tg, "settings", SimpleNamespace(tg_api_id=0, tg_api_hash="", request_delay=0.1, tg_session_path="")
    )
    with pytest.raises(RuntimeError):
        tg._require_api()
