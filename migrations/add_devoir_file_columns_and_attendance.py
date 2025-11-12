"""
Migration idempotente:
- ajoute les colonnes file_name, file_path dans table 'devoirs' si manquantes
- crée la table 'attendances' si elle n'existe pas

Usage:
    python migrations/add_devoir_file_columns_and_attendance.py
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
        print(f"[migration] DB not found at {DB_PATH} — create it by running the app once.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        # add columns to devoirs if missing
        if table_exists(conn, "devoirs"):
            if not column_exists(conn, "devoirs", "file_name"):
                print("[migration] Adding column file_name to devoirs")
                conn.execute("ALTER TABLE devoirs ADD COLUMN file_name TEXT;")
            else:
                print("[migration] file_name already exists")
            if not column_exists(conn, "devoirs", "file_path"):
                print("[migration] Adding column file_path to devoirs")
                conn.execute("ALTER TABLE devoirs ADD COLUMN file_path TEXT;")
            else:
                print("[migration] file_path already exists")
        else:
            print("[migration] Table 'devoirs' does not exist yet. Skipping column additions.")

        # create attendances table if not exists
        if not table_exists(conn, "attendances"):
            print("[migration] Creating table attendances")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendances (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    evenement_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT
                );
            """)
        else:
            print("[migration] attendances already exists")

        conn.commit()
        print("[migration] Done")
    except Exception as e:
        print("[migration] Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()