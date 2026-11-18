import json

from froshgah.db import Database
from froshgah.export import import_json
from froshgah.run import _split, run_job


def test_split():
    assert _split("a, b ,,c") == ["a", "b", "c"]
    assert _split("# پوشاک ,مانتو") == ["پوشاک", "مانتو"]
    assert _split("") == []


def test_run_job_offline_no_network(tmp_path, monkeypatch):
    """اجرای کامل بدون جمع‌آورندها (شبکه در این سندباکس نیست) — فقط ادغام + JSON + سایت."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "run.db"))
    seed = tmp_path / "data" / "stores.json"
    seed.parent.mkdir()
    seed.write_text(json.dumps({"stores": [
        {"source": "instagram", "source_key": "old", "title": "رکورد قبلی", "city": "تهران"},
    ]}), encoding="utf-8")

    db = Database(tmp_path / "run.db")
    db.init()
    summary = run_job(
        instagram_tags="",
        telegram_queries="",
        data_file=seed,
        site_dir=tmp_path / "docs",
        db=db,
    )
    assert summary["merged_from_cache"] == 1
    assert summary["stores_total"] == 1
    assert json.loads(seed.read_text(encoding="utf-8"))["count"] == 1
    assert (tmp_path / "docs" / "index.html").exists()


def test_run_job_reports_errors_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "run2.db"))
    from types import SimpleNamespace

    from froshgah import run as run_module

    monkeypatch.setattr(run_module, "settings", SimpleNamespace(tg_api_id=0, tg_api_hash=""))
    data = tmp_path / "d.json"
    summary = run_job(telegram_queries="پوشاک", limit=5, data_file=data, site_dir=None,
                      db=Database(tmp_path / "run2.db"))
    assert any("تلگرام" in e for e in summary["telegram"]["errors"])
    assert data.exists()
