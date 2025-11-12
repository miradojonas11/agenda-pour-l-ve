"""
Script de migration léger pour ajouter les colonnes 'file_name' et 'file_path'
dans la table 'devoirs' de agenda.db si elles n'existent pas.

Usage:
    python migrations/add_devoir_file_columns.py

Remarque:
- Ce script utilise sqlite3 et fonctionne sans SQLAlchemy.
- Il est idempotent : exécute-le autant de fois que nécessaire.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "agenda.db"

def column_exists(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    cols = [row[1] for row in cur.fetchall()]  # row[1] = name
    return column in cols

def main():
    if not DB_PATH.exists():
        print(f"[migration] Base de données non trouvée ({DB_PATH}). Rien à migrer.")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        changed = False
        if not column_exists(conn, "devoirs", "file_name"):
            print("[migration] Ajout de la colonne 'file_name'...")
            conn.execute("ALTER TABLE devoirs ADD COLUMN file_name TEXT;")
            changed = True
        else:
            print("[migration] Colonne 'file_name' déjà présente.")
        if not column_exists(conn, "devoirs", "file_path"):
            print("[migration] Ajout de la colonne 'file_path'...")
            conn.execute("ALTER TABLE devoirs ADD COLUMN file_path TEXT;")
            changed = True
        else:
            print("[migration] Colonne 'file_path' déjà présente.")
        if changed:
            conn.commit()
            print("[migration] Migration terminée avec succès.")
        else:
            print("[migration] Aucune modification nécessaire.")
    except Exception as e:
        print("[migration] Erreur lors de la migration :", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()