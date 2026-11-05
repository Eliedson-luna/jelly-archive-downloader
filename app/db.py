"""Persistência em SQLite: configurações, cache e histórico."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downloads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier  TEXT NOT NULL,
    title       TEXT NOT NULL,
    torrent_url TEXT NOT NULL,
    info_hash   TEXT,
    category    TEXT,
    savepath    TEXT,
    status      TEXT NOT NULL DEFAULT 'added',
    progress    REAL NOT NULL DEFAULT 0,
    size        INTEGER NOT NULL DEFAULT 0,
    added_at    TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    last_error  TEXT
);

CREATE INDEX IF NOT EXISTS idx_downloads_hash ON downloads(info_hash);
CREATE INDEX IF NOT EXISTS idx_downloads_added ON downloads(added_at DESC);

CREATE TABLE IF NOT EXISTS metadata_cache (
    identifier TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
"""

BASE_DEFAULTS = {
    "download_dir": "",
    "qbittorrent_url": "http://127.0.0.1:8080",
    "qbittorrent_user": "admin",
    "qbittorrent_password": "",
    "category": "jelly",
    "add_paused": "0",
    "rows_per_page": "30",
    "request_timeout": "15",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DB_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        g.db = conn
    return g.db


def close_db(_exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _defaults() -> dict:
    defaults = dict(BASE_DEFAULTS)
    defaults["search_url"] = current_app.config["DEFAULT_SEARCH_URL"]
    return defaults


def _seed_defaults(conn: sqlite3.Connection) -> None:
    now = utcnow()
    for key, value in _defaults().items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )


def _apply_env(conn: sqlite3.Connection) -> None:
    """Variáveis de ambiente não vazias sobrescrevem o que está no banco."""
    now = utcnow()
    for key, env_name in current_app.config["ENV_MANAGED"].items():
        value = os.environ.get(env_name)
        if not value:
            continue
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                           updated_at = excluded.updated_at
            """,
            (key, value, now),
        )


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        conn = get_db()
        conn.executescript(SCHEMA)
        _seed_defaults(conn)
        _apply_env(conn)
        conn.commit()


# --------------------------------------------------------------------------
# settings
# --------------------------------------------------------------------------


def get_setting(key: str, default: str = "") -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_settings() -> dict:
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    values = dict(_defaults())
    values.update({row["key"]: row["value"] for row in rows})
    return values


def set_setting(key: str, value: str) -> None:
    get_db().execute(
        """
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                       updated_at = excluded.updated_at
        """,
        (key, value, utcnow()),
    )


def env_managed_keys() -> dict:
    """Chaves forçadas por variável de ambiente -> nome da variável."""
    return {
        key: env_name
        for key, env_name in current_app.config["ENV_MANAGED"].items()
        if os.environ.get(env_name)
    }


# --------------------------------------------------------------------------
# downloads
# --------------------------------------------------------------------------


def add_download(
    *,
    identifier: str,
    title: str,
    torrent_url: str,
    info_hash: str,
    category: str,
    savepath: str,
    size: int = 0,
) -> int:
    now = utcnow()
    cur = get_db().execute(
        """
        INSERT INTO downloads
            (identifier, title, torrent_url, info_hash, category, savepath,
             status, progress, size, added_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'added', 0, ?, ?, ?)
        """,
        (identifier, title, torrent_url, info_hash, category, savepath, size, now, now),
    )
    get_db().commit()
    return int(cur.lastrowid)


def list_downloads(limit: int = 200) -> list:
    rows = get_db().execute(
        "SELECT * FROM downloads ORDER BY added_at DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_download(download_id: int):
    row = get_db().execute("SELECT * FROM downloads WHERE id = ?", (download_id,)).fetchone()
    return dict(row) if row else None


def find_by_hash(info_hash: str):
    row = get_db().execute(
        "SELECT * FROM downloads WHERE info_hash = ? ORDER BY id DESC LIMIT 1", (info_hash,)
    ).fetchone()
    return dict(row) if row else None


def update_download(download_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = utcnow()
    columns = ", ".join(f"{name} = ?" for name in fields)
    values = list(fields.values()) + [download_id]
    get_db().execute(f"UPDATE downloads SET {columns} WHERE id = ?", values)
    get_db().commit()


def delete_download(download_id: int) -> None:
    get_db().execute("DELETE FROM downloads WHERE id = ?", (download_id,))
    get_db().commit()


# --------------------------------------------------------------------------
# cache de metadados
# --------------------------------------------------------------------------


def cache_get(identifier: str, ttl: int) -> dict | None:
    import json

    row = get_db().execute(
        "SELECT payload, fetched_at FROM metadata_cache WHERE identifier = ?", (identifier,)
    ).fetchone()
    if not row:
        return None
    try:
        fetched = datetime.strptime(row["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    if age > ttl:
        return None
    try:
        return json.loads(row["payload"])
    except ValueError:
        return None


def cache_put(identifier: str, payload: dict) -> None:
    import json

    get_db().execute(
        """
        INSERT INTO metadata_cache (identifier, payload, fetched_at) VALUES (?, ?, ?)
        ON CONFLICT(identifier) DO UPDATE SET payload = excluded.payload,
                                              fetched_at = excluded.fetched_at
        """,
        (identifier, json.dumps(payload), utcnow()),
    )
    get_db().commit()
