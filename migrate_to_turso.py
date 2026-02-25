"""One-time migration: copy local SQLite expenses to Turso cloud database.

Usage:
    python migrate_to_turso.py

Requires environment variables (or edit the values below):
    TURSO_DATABASE_URL  — e.g. libsql://your-db.turso.io
    TURSO_AUTH_TOKEN    — your Turso auth token
"""

import os
import sqlite3
import libsql_experimental as libsql

# --- Local source ---
LOCAL_DB = os.path.join(os.path.dirname(__file__), "data", "expenses.db")

# --- Turso target ---
TURSO_URL = os.environ["TURSO_DATABASE_URL"]
TURSO_TOKEN = os.environ["TURSO_AUTH_TOKEN"]


def migrate():
    # Connect to local SQLite
    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row
    rows = local.execute(
        "SELECT date, amount, category, description, added_by FROM expenses ORDER BY id"
    ).fetchall()
    local.close()
    print(f"Read {len(rows)} expenses from local DB")

    if not rows:
        print("Nothing to migrate.")
        return

    # Connect to Turso
    remote = libsql.connect("migration.db", sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
    remote.sync()

    # Ensure table exists
    remote.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            added_by TEXT DEFAULT 'unknown'
        )
    """)
    remote.commit()

    # Insert rows
    for r in rows:
        remote.execute(
            "INSERT INTO expenses (date, amount, category, description, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (r["date"], r["amount"], r["category"], r["description"], r["added_by"]),
        )
    remote.commit()
    remote.sync()
    remote.close()
    print(f"Migrated {len(rows)} expenses to Turso successfully!")


if __name__ == "__main__":
    migrate()
