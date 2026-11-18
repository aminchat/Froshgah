"""ذخیره‌سازی و جستجوی فروشگاه‌ها با SQLite."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .config import settings
from .models import Store
from .normalize import normalize

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    title TEXT DEFAULT '',
    username TEXT DEFAULT '',
    url TEXT DEFAULT '',
    text TEXT DEFAULT '',
    phones TEXT DEFAULT '[]',
    instagram TEXT DEFAULT '',
    telegram TEXT DEFAULT '',
    website TEXT DEFAULT '',
    city TEXT DEFAULT '',
    categories TEXT DEFAULT '[]',
    first_seen TEXT DEFAULT '',
    last_seen TEXT DEFAULT '',
    UNIQUE(source, source_key)
);
CREATE INDEX IF NOT EXISTS idx_stores_username ON stores(username);
"""

_FIELDS = (
    "id", "source", "source_key", "title", "username", "url", "text",
    "phones", "instagram", "telegram", "website", "city", "categories",
    "first_seen", "last_seen",
)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = {k: row[k] for k in _FIELDS}
    d["phones"] = json.loads(d["phones"] or "[]")
    d["categories"] = json.loads(d["categories"] or "[]")
    for k in ("title", "username", "url", "text", "instagram", "telegram", "website", "city"):
        d[k] = d[k] or ""
    return d


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(settings.db_path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ——— نوشتن ———
    def upsert(self, store: Store) -> None:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM stores WHERE source = ? AND source_key = ?",
                (store.source, store.source_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO stores (source, source_key, title, username, url, text,"
                    " phones, instagram, telegram, website, city, categories, first_seen, last_seen)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        store.source, store.source_key, store.title, store.username,
                        store.url, store.text, json.dumps(store.phones, ensure_ascii=False),
                        store.instagram, store.telegram, store.website, store.city,
                        json.dumps(store.categories, ensure_ascii=False), now, now,
                    ),
                )
                return
            phones = _dedupe(json.loads(row["phones"] or "[]") + store.phones)
            cats = _dedupe(json.loads(row["categories"] or "[]") + store.categories)
            text = row["text"] if len(row["text"] or "") >= len(store.text or "") else store.text
            conn.execute(
                "UPDATE stores SET title=?, username=?, url=?, text=?, phones=?,"
                " instagram=?, telegram=?, website=?, city=?, categories=?, last_seen=? WHERE id=?",
                (
                    row["title"] or store.title,
                    row["username"] or store.username,
                    row["url"] or store.url,
                    text,
                    json.dumps(phones, ensure_ascii=False),
                    row["instagram"] or store.instagram,
                    row["telegram"] or store.telegram,
                    row["website"] or store.website,
                    row["city"] or store.city,
                    json.dumps(cats, ensure_ascii=False),
                    now,
                    row["id"],
                ),
            )

    # ——— خواندن ———
    def _all_rows(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM stores ORDER BY last_seen DESC").fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_all(self) -> list[dict]:
        return self._all_rows()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        tokens = [t for t in normalize(query).split() if t]
        if not tokens:
            return []
        scored: list[tuple] = []
        for d in self._all_rows():
            blob = normalize(
                " ".join(
                    [
                        d["title"], d["username"], d["text"], d["city"],
                        " ".join(d["categories"]), " ".join(d["phones"]),
                        d["url"], d["instagram"], d["telegram"], d["website"],
                        d["source_key"],
                    ]
                )
            )
            hits = sum(1 for t in tokens if t in blob)
            if hits == 0:
                continue
            full = hits == len(tokens)
            scored.append((full, hits, len(d["phones"]), d["last_seen"], d))
        scored.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
        return [x[-1] for x in scored[:limit]]

    def latest(self, limit: int = 10) -> list[dict]:
        return self._all_rows()[:limit]

    def stats(self) -> dict:
        rows = self._all_rows()
        return {
            "total": len(rows),
            "instagram": sum(1 for r in rows if r["source"] == "instagram"),
            "telegram": sum(1 for r in rows if r["source"] == "telegram"),
            "with_phone": sum(1 for r in rows if r["phones"]),
            "path": str(self.path),
        }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def get_db() -> Database:
    db = Database()
    db.init()
    return db
