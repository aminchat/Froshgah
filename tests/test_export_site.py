import json
from pathlib import Path

from froshgah.db import Database
from froshgah.export import export_json, import_json
from froshgah.models import Store
from froshgah.site import build_site


def make_db(tmp_path):
    db = Database(tmp_path / "t.db")
    db.init()
    return db


def test_export_roundtrip_keeps_seen_and_merges(tmp_path):
    db = make_db(tmp_path)
    db.upsert(Store(source="instagram", source_key="a", title="پوشاک آریا",
                    city="تهران", phones=["09121112233"], categories=["پوشاک"]))
    path = export_json(db, tmp_path / "data" / "stores.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["count"] == 1
    assert payload["stores"][0]["phones"] == ["09121112233"]
    assert payload["stores"][0]["first_seen"]

    # ادغام در یک دیتابیس خالی دیگر
    db2 = make_db(tmp_path.parent / "db2")
    n = import_json(db2, path)
    assert n == 1
    rows = db2.get_all()
    assert rows[0]["title"] == "پوشاک آریا"
    assert rows[0]["first_seen"] == payload["stores"][0]["first_seen"]

    # اجرای دوم: رکورد جدید اضافه می‌شود، قبلی از بین نمی‌رود
    db2.upsert(Store(source="telegram", source_key="b", title="بوتیک ب", city="شیراز"))
    export_json(db2, path)
    assert db2.stats()["total"] == 2
    assert json.loads(path.read_text(encoding="utf-8"))["count"] == 2


def test_import_missing_or_broken_file(tmp_path):
    db = make_db(tmp_path)
    assert import_json(db, tmp_path / "nope.json") == 0
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert import_json(db, bad) == 0
    bad.write_text(json.dumps({"stores": [{"nonsense": 1}]}), encoding="utf-8")
    assert import_json(db, bad) == 0


def test_build_site_copies_assets_and_data(tmp_path):
    db = make_db(tmp_path)
    db.upsert(Store(source="telegram", source_key="s", title="فروشگاه نمونه", phones=["09120000000"]))
    data_file = tmp_path / "data" / "stores.json"
    out = build_site(db, data_file, tmp_path / "docs")
    assert (out / "index.html").exists()
    assert (out / "app.js").exists()
    assert (out / "style.css").exists()
    assert (out / ".nojekyll").exists()
    assert json.loads((out / "data" / "stores.json").read_text(encoding="utf-8"))["count"] == 1
    assert json.loads(data_file.read_text(encoding="utf-8"))["count"] == 1


def test_build_site_same_file_target(tmp_path):
    """اگر فایل داده داخل پوشه سایت باشد، نباید خطای SameFileError بدهد."""
    db = make_db(tmp_path)
    out = build_site(db, tmp_path / "site" / "data" / "stores.json", tmp_path / "site")
    assert isinstance(out, Path) and out.exists()
