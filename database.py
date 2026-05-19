import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "linktracker.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                email   TEXT    UNIQUE NOT NULL,
                name    TEXT    NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS links (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id),
                page_url        TEXT    NOT NULL,
                expected_link_url  TEXT NOT NULL,
                expected_anchor    TEXT NOT NULL,
                notes           TEXT DEFAULT '',
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_checked    DATETIME,
                -- check results (NULL = never checked, 1 = pass, 0 = fail)
                check_status_200    INTEGER,
                check_crawlable     INTEGER,
                check_indexable     INTEGER,
                check_canonical     INTEGER,
                check_anchor_found  INTEGER,
                check_url_match     INTEGER,
                check_errors        TEXT DEFAULT ''
            );
        """)


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(email: str, name: str, password_hash: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
            (email.lower().strip(), name.strip(), password_hash),
        )


def get_user_by_email(email: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users():
    with get_db() as conn:
        return conn.execute("SELECT id, email, name FROM users ORDER BY name").fetchall()


# ── Links ──────────────────────────────────────────────────────────────────

def create_link(user_id: int, page_url: str, expected_link_url: str,
                expected_anchor: str, notes: str = ""):
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO links
               (user_id, page_url, expected_link_url, expected_anchor, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, page_url.strip(), expected_link_url.strip(),
             expected_anchor.strip(), notes.strip()),
        )
        return cur.lastrowid


def get_link(link_id: int):
    with get_db() as conn:
        return conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()


def list_links(user_id: int | None = None):
    with get_db() as conn:
        if user_id:
            return conn.execute(
                """SELECT l.*, u.name as user_name
                   FROM links l JOIN users u ON l.user_id = u.id
                   WHERE l.user_id = ?
                   ORDER BY l.created_at DESC""",
                (user_id,),
            ).fetchall()
        return conn.execute(
            """SELECT l.*, u.name as user_name
               FROM links l JOIN users u ON l.user_id = u.id
               ORDER BY l.created_at DESC"""
        ).fetchall()


def update_link_check(link_id: int, results: dict):
    with get_db() as conn:
        conn.execute(
            """UPDATE links SET
               last_checked       = CURRENT_TIMESTAMP,
               check_status_200   = ?,
               check_crawlable    = ?,
               check_indexable    = ?,
               check_canonical    = ?,
               check_anchor_found = ?,
               check_url_match    = ?,
               check_errors       = ?
               WHERE id = ?""",
            (
                int(results["status_200"]) if results["status_200"] is not None else None,
                int(results["crawlable"]) if results["crawlable"] is not None else None,
                int(results["indexable"]) if results["indexable"] is not None else None,
                int(results["canonical_self"]) if results["canonical_self"] is not None else None,
                int(results["anchor_found"]) if results["anchor_found"] is not None else None,
                int(results["url_match"]) if results["url_match"] is not None else None,
                "\n".join(results.get("errors", [])),
                link_id,
            ),
        )


def update_link(link_id: int, page_url: str, expected_link_url: str,
                expected_anchor: str, notes: str, user_id: int):
    with get_db() as conn:
        conn.execute(
            """UPDATE links SET
               page_url = ?, expected_link_url = ?, expected_anchor = ?, notes = ?
               WHERE id = ? AND user_id = ?""",
            (page_url.strip(), expected_link_url.strip(),
             expected_anchor.strip(), notes.strip(), link_id, user_id),
        )


def delete_link(link_id: int, user_id: int):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM links WHERE id = ? AND user_id = ?", (link_id, user_id)
        )


def get_all_link_ids():
    with get_db() as conn:
        rows = conn.execute("SELECT id FROM links").fetchall()
        return [r["id"] for r in rows]
