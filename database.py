"""Turso (libsql) CRUD operations for the expense tracker.

Uses a single cached connection to avoid the overhead of connecting and
syncing on every call.  The local replica is stored in a temp directory
so the path is stable on Streamlit Cloud.
"""

import tempfile
import os
import logging
from datetime import date, datetime

import libsql_experimental as libsql
import streamlit as st

logger = logging.getLogger(__name__)

_COLUMNS = ["id", "date", "amount", "category", "description", "added_by"]

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_cached_connection():
    """Return a long-lived libsql connection (one per app lifetime)."""
    url = st.secrets["TURSO_DATABASE_URL"]
    token = st.secrets["TURSO_AUTH_TOKEN"]
    db_path = os.path.join(tempfile.gettempdir(), "expense_tracker_replica.db")
    conn = libsql.connect(db_path, sync_url=url, auth_token=token)
    conn.sync()
    return conn


def get_connection():
    """Get the cached connection, recovering on failure."""
    try:
        conn = _get_cached_connection()
        return conn
    except Exception:
        logger.exception("Connection error — clearing cache and retrying")
        _get_cached_connection.clear()
        return _get_cached_connection()


def _sync_read(conn):
    """Sync before a read so we see the latest remote data."""
    try:
        conn.sync()
    except Exception:
        logger.warning("Sync before read failed", exc_info=True)


def _sync_write(conn):
    """Commit + sync after a write so changes reach the remote."""
    try:
        conn.commit()
        conn.sync()
    except Exception:
        logger.exception("Sync after write failed — clearing connection cache")
        _get_cached_connection.clear()
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows) -> list[dict]:
    """Convert tuple rows to dicts using the standard column list."""
    return [dict(zip(_COLUMNS, row)) for row in rows]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL UNIQUE,
            monthly_limit REAL NOT NULL,
            updated_by TEXT DEFAULT 'unknown',
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            frequency TEXT NOT NULL DEFAULT 'monthly',
            day_of_month INTEGER DEFAULT 1,
            added_by TEXT DEFAULT 'unknown',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_added_date TEXT
        )
    """)
    _sync_write(conn)


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------

def add_expense(date_val: date, amount: float, category: str, description: str, added_by: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO expenses (date, amount, category, description, added_by) VALUES (?, ?, ?, ?, ?)",
        (date_val.isoformat(), round(amount, 2), category, description, added_by),
    )
    _sync_write(conn)


def delete_expense(expense_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    _sync_write(conn)


def get_expenses_between(start_date: date, end_date: date) -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return _rows_to_dicts(rows)


def get_recent_expenses(limit: int = 10) -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------

def get_budgets() -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        "SELECT category, monthly_limit, updated_by, updated_at FROM budgets ORDER BY category"
    ).fetchall()
    return [dict(zip(["category", "monthly_limit", "updated_by", "updated_at"], r)) for r in rows]


def set_budget(category: str, monthly_limit: float, updated_by: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO budgets (category, monthly_limit, updated_by, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(category) DO UPDATE SET
               monthly_limit = excluded.monthly_limit,
               updated_by = excluded.updated_by,
               updated_at = datetime('now')""",
        (category, round(monthly_limit, 2), updated_by),
    )
    _sync_write(conn)


def get_monthly_category_totals(year: int, month: int) -> dict[str, float]:
    """Return {category: total_spent} for a given month via SQL aggregation."""
    conn = get_connection()
    _sync_read(conn)
    start = f"{year:04d}-{month:02d}-01"
    # last day
    import calendar as _cal
    last_day = _cal.monthrange(year, month)[1]
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    rows = conn.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE date >= ? AND date <= ? GROUP BY category",
        (start, end),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Recurring expenses CRUD
# ---------------------------------------------------------------------------

def add_recurring_expense(name: str, amount: float, category: str, description: str,
                          frequency: str, day_of_month: int, added_by: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO recurring_expenses
           (name, amount, category, description, frequency, day_of_month, added_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, round(amount, 2), category, description, frequency, day_of_month, added_by),
    )
    _sync_write(conn)


def get_recurring_expenses(active_only: bool = True) -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    cols = ["id", "name", "amount", "category", "description", "frequency",
            "day_of_month", "added_by", "active", "created_at", "last_added_date"]
    where = "WHERE active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT {', '.join(cols)} FROM recurring_expenses {where} ORDER BY name"
    ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def deactivate_recurring_expense(expense_id: int):
    conn = get_connection()
    conn.execute("UPDATE recurring_expenses SET active = 0 WHERE id = ?", (expense_id,))
    _sync_write(conn)


def update_recurring_last_added(expense_id: int, last_date: str):
    conn = get_connection()
    conn.execute(
        "UPDATE recurring_expenses SET last_added_date = ? WHERE id = ?",
        (last_date, expense_id),
    )
    _sync_write(conn)


def process_recurring_expenses():
    """Auto-add due recurring expenses. Uses last_added_date to prevent doubles."""
    today = date.today()
    recurring = get_recurring_expenses(active_only=True)

    for rec in recurring:
        last_added = rec["last_added_date"]
        if last_added:
            last_dt = datetime.strptime(last_added, "%Y-%m-%d").date()
        else:
            last_dt = None

        should_add = False

        if rec["frequency"] == "monthly":
            if last_dt is None or (last_dt.year < today.year or
                                    (last_dt.year == today.year and last_dt.month < today.month)):
                if today.day >= rec["day_of_month"]:
                    should_add = True

        elif rec["frequency"] == "weekly":
            if last_dt is None or (today - last_dt).days >= 7:
                should_add = True

        elif rec["frequency"] == "biweekly":
            if last_dt is None or (today - last_dt).days >= 14:
                should_add = True

        if should_add:
            add_expense(
                today, rec["amount"], rec["category"],
                f"[Recurring] {rec['name']}" + (f" — {rec['description']}" if rec["description"] else ""),
                rec["added_by"],
            )
            update_recurring_last_added(rec["id"], today.isoformat())
