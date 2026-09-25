import sqlite3
import os
import threading

# База хранится в /app/data (DATA_DIR) на хостинге, чтобы не теряться при рестарте.
# Локально при отсутствии переменной — в папке проекта.
_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "shop.db")

_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                game TEXT NOT NULL DEFAULT 'mm2',
                seller TEXT NOT NULL DEFAULT 'mont1g3m',
                img TEXT,
                photos INTEGER DEFAULT 1,
                desc TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                PRIMARY KEY (user, item_id)
            )
        """)
        conn.commit()
        conn.close()


def list_items():
    with _lock:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
        conn.close()
        return [dict(r) for r in rows]


def get_item(item_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        conn.close()
        return dict(row) if row else None


def add_item(name, price, game, seller, img, photos, desc):
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO items (name, price, game, seller, img, photos, desc) VALUES (?,?,?,?,?,?,?)",
            (name, price, game, seller, img, photos or 1, desc or ""),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return new_id


def delete_item(item_id):
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.close()


def get_favs(user):
    with _lock:
        conn = get_conn()
        rows = conn.execute(
            "SELECT item_id FROM favorites WHERE user=?", (user,)
        ).fetchall()
        conn.close()
        return [r["item_id"] for r in rows]


def toggle_fav(user, item_id):
    with _lock:
        conn = get_conn()
        exists = conn.execute(
            "SELECT 1 FROM favorites WHERE user=? AND item_id=?",
            (user, item_id),
        ).fetchone()
        if exists:
            conn.execute(
                "DELETE FROM favorites WHERE user=? AND item_id=?",
                (user, item_id),
            )
            removed = True
        else:
            conn.execute(
                "INSERT OR IGNORE INTO favorites (user, item_id) VALUES (?,?)",
                (user, item_id),
            )
            removed = False
        conn.commit()
        conn.close()
        return {"favorite": not removed}
