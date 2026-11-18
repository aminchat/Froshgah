"""تست رمزنگاری بار پنل وب و ساخت پوشه Vercel."""
import json
from pathlib import Path

import pytest

from froshgah import config
from froshgah.db import Database
from froshgah.models import Store
from froshgah.payload import decrypt, encrypt, load_payload, post_json
from froshgah.run import apply_payload
from froshgah.site import build_site

SECRET = "unit-test-app-secret"


def test_encrypt_decrypt_roundtrip():
    data = {"ig_user": "nika", "ig_pass": "رمز مخفی", "hashtags": ["پوشاک"], "limit": 25}
    token = encrypt(data, SECRET)
    assert "رمز مخفی" not in token
    assert decrypt(token, SECRET) == data


def test_wrong_key_or_tampered_payload_fails():
    token = encrypt({"a": 1}, SECRET)
    with pytest.raises(Exception):
        decrypt(token, "denseh-e-dig")
    raw = list(__import__("base64").b64decode(token))
    raw[-1] ^= 0xFF
    with pytest.raises(Exception):
        decrypt(__import__("base64").b64encode(bytes(raw)).decode(), SECRET)


def test_load_payload_from_file(tmp_path: Path):
    f = tmp_path / "p.txt"
    f.write_text("  abcd==\n", encoding="utf-8")
    assert load_payload(f"@{f}") == "abcd=="
    assert load_payload("  xyz ") == "xyz"
    assert load_payload("") == ""


def test_apply_payload_sets_settings_and_session(tmp_path: Path, monkeypatch):
    session = tmp_path / "froshgah.session"
    session.write_bytes(b"SQLITEFAKE")
    import base64

    applied = apply_payload({
        "ig_user": "nika", "ig_pass": "pass", "tg_api_id": "۱۲۳۴۵", "tg_api_hash": "abc",
        "tg_session": base64.b64encode(session.read_bytes()).decode(),
    })
    assert applied["IG_USERNAME"] == "set"
    assert applied["TG_SESSION"] == "set"
    assert config.settings.ig_username == "nika"
    assert config.settings.tg_api_id == 12345  # ارقام فارسی هم تبدیل می‌شود
    assert Path(config.settings.tg_session_path).parent.exists()
    assert (Path(config.settings.tg_session_path).parent / "froshgah.session").read_bytes() == b"SQLITEFAKE"
    assert apply_payload({}) == {}

    # برگرداندن تنظیمات به حالت اول
    monkeypatch.setattr(config, "settings", config.get_settings())


def test_post_json_stub():
    seen = {}

    class Resp:
        status = 200

    def opener(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("X-froshgah-token")
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return Resp()

    ok, detail = post_json("https://example.com/api/ingest", "tok", {"count": 3}, opener=opener)
    assert ok and detail == "HTTP 200"
    assert seen["auth"] == "tok" and seen["body"]["count"] == 3
    assert seen["url"].endswith("/api/ingest")


def test_post_json_failure_is_quiet():
    def opener(req, timeout=None):
        raise OSError("down")

    ok, detail = post_json("https://example.com/x", "", {"a": 1}, opener=opener)
    assert ok is False and "down" in detail


def test_build_site_vercel_injects_config(tmp_path: Path):
    db = Database(tmp_path / "t.db")
    db.init()
    db.upsert(Store(source="telegram", source_key="a", title="فروشگاه"))
    out = build_site(db, tmp_path / "data/stores.json", tmp_path / "vercel", public=True)
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "window.FROSHGAH=" in html and '"/api/data"' in html
    assert (out / "api" / "index.js").exists() is False  # فقط فایل‌های وب کپی می‌شوند
    # داده نباید کنار فایل‌های عمومی بنشیند، وگرنه از قفل لاگین رد می‌زند
    assert not (out / "data").exists()
    assert json.loads((tmp_path / "data/stores.json").read_text(encoding="utf-8"))["count"] == 1

    # نسخه Pages نباید تنظیم سرویس را داشته باشد
    pages = build_site(db, tmp_path / "data/stores.json", tmp_path / "docs")
    assert "window.FROSHGAH" not in (pages / "index.html").read_text(encoding="utf-8")
