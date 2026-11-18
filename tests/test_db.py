from froshgah.db import Database
from froshgah.models import Store


def make_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init()
    return db


def test_upsert_and_merge(tmp_path):
    db = make_db(tmp_path)
    db.upsert(
        Store(
            source="instagram",
            source_key="shop1",
            title="Shop One",
            username="shop1",
            phones=["09121112233"],
            categories=["پوشاک"],
        )
    )
    db.upsert(
        Store(
            source="instagram",
            source_key="shop1",
            title="Shop One",
            username="shop1",
            phones=["09351112233"],
            categories=["مانتو"],
            text="مانتو تهران",
        )
    )
    rows = db.get_all()
    assert len(rows) == 1
    assert set(rows[0]["phones"]) == {"09121112233", "09351112233"}
    assert set(rows[0]["categories"]) == {"پوشاک", "مانتو"}
    assert rows[0]["text"] == "مانتو تهران"


def test_search_found_and_miss(tmp_path):
    db = make_db(tmp_path)
    db.upsert(
        Store(
            source="telegram",
            source_key="a",
            title="فروشگاه پوشاک زنانه",
            text="مانتو و شلوار - تهران",
            phones=["09120001122"],
            city="تهران",
            categories=["پوشاک", "مانتو"],
        )
    )
    db.upsert(
        Store(
            source="instagram",
            source_key="b",
            title="بوتیک کفش",
            text="کفش اسپرت مردانه اهواز",
            city="اهواز",
            categories=["کفش"],
        )
    )
    r1 = db.search("پوشاک")
    assert len(r1) == 1 and r1[0]["source_key"] == "a"
    r2 = db.search("مانتو تهران")
    assert len(r2) == 1 and r2[0]["source_key"] == "a"
    r3 = db.search("کفش")
    assert len(r3) == 1 and r3[0]["source_key"] == "b"
    assert db.search("یخچال") == []
    assert db.search("") == []


def test_search_by_phone_digits(tmp_path):
    db = make_db(tmp_path)
    db.upsert(Store(source="telegram", source_key="p", title="x", phones=["09121234567"]))
    rows = db.search("۰۹۱۲۱۲۳۴۵۶۷")
    assert len(rows) == 1


def test_latest_and_stats(tmp_path):
    db = make_db(tmp_path)
    assert db.stats()["total"] == 0
    db.upsert(Store(source="instagram", source_key="x", title="a", phones=["09121112233"]))
    db.upsert(Store(source="telegram", source_key="y", title="b"))
    s = db.stats()
    assert s["total"] == 2
    assert s["instagram"] == 1
    assert s["telegram"] == 1
    assert s["with_phone"] == 1
    assert len(db.latest(10)) == 2
