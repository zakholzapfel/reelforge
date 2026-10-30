"""Small transactional queue; recover interrupted jobs without rerunning automatically."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE, payload TEXT NOT NULL, state TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created REAL NOT NULL)")
            self.db.execute("UPDATE jobs SET state='paused', detail='Interrupted; resume to continue.' WHERE state IN ('queued','running','merging')")
            self.db.execute("CREATE TABLE IF NOT EXISTS date_cache (url TEXT PRIMARY KEY, title TEXT NOT NULL, dating TEXT NOT NULL, description TEXT NOT NULL, upload_date TEXT NOT NULL, updated REAL NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def add(self, payload: dict, fingerprint: str):
        with self.lock, self.db:
            old = self.db.execute("SELECT id FROM jobs WHERE fingerprint=?", (fingerprint,)).fetchone()
            if old:
                return old["id"], False
            jid = uuid.uuid4().hex
            self.db.execute("INSERT INTO jobs(id,fingerprint,payload,state,created) VALUES(?,?,?,'queued',?)", (jid, fingerprint, json.dumps(payload), time.time()))
            return jid, True

    def update(self, jid: str, **values):
        allowed = {"state", "progress", "detail", "error"}
        if not values or not set(values) <= allowed:
            raise ValueError("Invalid queue update.")
        with self.lock, self.db:
            self.db.execute("UPDATE jobs SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?", (*values.values(), jid))

    def rows(self):
        with self.lock:
            rows = self.db.execute("SELECT * FROM jobs ORDER BY created").fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def get(self, jid):
        with self.lock:
            row = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        return dict(row) | {"payload": json.loads(row["payload"])} if row else None

    def close(self):
        with self.lock:
            self.db.close()

    def cache_date(self, item):
        with self.lock, self.db:
            self.db.execute("INSERT INTO date_cache VALUES(?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET title=excluded.title, dating=excluded.dating, description=excluded.description, upload_date=excluded.upload_date, updated=excluded.updated", (item.url, item.title, item.dating.model_dump_json(), item.description, item.upload_date, time.time()))

    def references(self):
        from .models import ReferenceCatalog
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key='references'").fetchone()
        return ReferenceCatalog.model_validate_json(row["value"]) if row else ReferenceCatalog()

    def save_references(self, catalog):
        with self.lock, self.db:
            self.db.execute("INSERT INTO settings VALUES('references',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (catalog.model_dump_json(),))

    def restored_date(self, item):
        from .models import Dating
        with self.lock:
            row = self.db.execute("SELECT * FROM date_cache WHERE url=? AND title=?", (item.url, item.title)).fetchone()
        if row:
            item = item.model_copy(deep=True)
            item.dating = Dating.model_validate_json(row["dating"])
            item.description = row["description"]
            item.upload_date = row["upload_date"]
            if item.dating.reviewed and item.dating.year_start == item.dating.year_end:
                item.year = item.dating.year_start
        return item
