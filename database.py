"""Turso (libsql) CRUD operations for the expense tracker."""

import libsql_experimental as libsql
import streamlit as st
from datetime import date

_COLUMNS = ["id", "date", "amount", "category", "description", "added_by"]


def get_connection():
    url = st.secrets["TURSO_DATABASE_URL"]
    token = st.secrets["TURSO_AUTH_TOKEN"]
    conn = libsql.connect("expenses.db", sync_url=url, auth_token=token)
    conn.sync()
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
    conn.sync()
    conn.close()


def add_expense(date_val: date, amount: float, category: str, description: str, added_by: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO expenses (date, amount, category, description, added_by) VALUES (?, ?, ?, ?, ?)",
        (date_val.isoformat(), round(amount, 2), category, description, added_by),
    )
    conn.commit()
    conn.sync()
    conn.close()


def delete_expense(expense_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.sync()
    conn.close()


def _rows_to_dicts(rows) -> list[dict]:
    """Convert tuple rows to dicts using the standard column list."""
    return [dict(zip(_COLUMNS, row)) for row in rows]


def get_expenses_between(start_date: date, end_date: date) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_recent_expenses(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)
