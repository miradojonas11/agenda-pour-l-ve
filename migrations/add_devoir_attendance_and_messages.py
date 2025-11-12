"""
Migration idempotente:
- ajoute la colonne 'devoir_id' à la table 'attendances' si manquante
- crée la table 'messages' si manquante

Usage:
    python migrations/add_devoir_attendance_and_messages.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "agenda.db"

def table_exists(conn, table):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
    return cur.fetchone() is not None

def column_exists(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols

def main():
    if not DB_PATH.exists():
        print(f"[migration] DB not found at {DB_PATH}. Run the app once to create schema, then run this migration.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        if table_exists(conn, "attendances"):
            if not column_exists(conn, "attendances", "devoir_id"):
                print("[migration] Adding column 'devoir_id' to attendances")
                conn.execute("ALTER TABLE attendances ADD COLUMN devoir_id INTEGER;")
            else:
                print("[migration] Column 'devoir_id' already present in attendances")
        else:
            print("[migration] Table 'attendances' does not exist yet; skipping colonne addition.")

        if not table_exists(conn, "messages"):
            print("[migration] Creating table 'messages'")
            conn.execute("""
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    to_user_id INTEGER NOT NULL,
                    from_user_id INTEGER,
                    subject TEXT NOT NULL,
                    content TEXT,
                    created_at TEXT,
                    read INTEGER DEFAULT 0
                );
            """)
        else:
            print("[migration] Table 'messages' already exists")

        conn.commit()
        print("[migration] Done")
    except Exception as e:
        print("[migration] Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()