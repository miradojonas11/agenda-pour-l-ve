"""
Migration idempotente: ajoute la colonne 'salle' dans la table 'evenements' si elle n'existe pas.

Usage:
    python migrations/add_evenement_salle.py
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
        if table_exists(conn, "evenements"):
            if not column_exists(conn, "evenements", "salle"):
                print("[migration] Adding column 'salle' to evenements")
                conn.execute("ALTER TABLE evenements ADD COLUMN salle TEXT;")
                conn.commit()
                print("[migration] Column 'salle' added.")
            else:
                print("[migration] Column 'salle' already exists.")
        else:
            print("[migration] Table 'evenements' does not exist yet. No changes made.")
    except Exception as e:
        print("[migration] Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()