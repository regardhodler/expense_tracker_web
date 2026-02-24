"""SQLite CRUD operations for the expense tracker."""

import sqlite3
import os
from datetime import date

# Support DATA_DIR env var for deployment (e.g. volume mount at /app/data)
_DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)
DB_PATH = os.path.join(_DATA_DIR, "expenses.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            added_by TEXT DEFAULT 'unknown'
        )
    """)
    conn.commit()
    conn.close()


def add_expense(date_val: date, amount: float, category: str, description: str, added_by: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO expenses (date, amount, category, description, added_by) VALUES (?, ?, ?, ?, ?)",
        (date_val.isoformat(), round(amount, 2), category, description, added_by),
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()


def get_expenses_between(start_date: date, end_date: date) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_expenses(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
