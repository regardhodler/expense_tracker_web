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
    # Migration: add start_date column for weekly/biweekly anchor
    try:
        conn.execute("ALTER TABLE recurring_expenses ADD COLUMN start_date TEXT")
    except Exception:
        pass  # column already exists

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


def get_expense_by_id(expense_id: int) -> dict | None:
    """Fetch a single expense by ID."""
    conn = get_connection()
    _sync_read(conn)
    row = conn.execute(
        "SELECT id, date, amount, category, description, added_by "
        "FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(_COLUMNS, row))


def update_expense(expense_id: int, date_val: date, amount: float, category: str, description: str):
    """Update an existing expense."""
    conn = get_connection()
    conn.execute(
        "UPDATE expenses SET date = ?, amount = ?, category = ?, description = ? WHERE id = ?",
        (date_val.isoformat(), round(amount, 2), category, description, expense_id),
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
                          frequency: str, day_of_month: int, added_by: str,
                          start_date: str | None = None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO recurring_expenses
           (name, amount, category, description, frequency, day_of_month, added_by, start_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, round(amount, 2), category, description, frequency, day_of_month, added_by, start_date),
    )
    _sync_write(conn)


def get_recurring_expenses(active_only: bool = True) -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    cols = ["id", "name", "amount", "category", "description", "frequency",
            "day_of_month", "added_by", "active", "created_at", "last_added_date", "start_date"]
    where = "WHERE active = 1" if active_only else ""
    rows = conn.execute(
        f"SELECT {', '.join(cols)} FROM recurring_expenses {where} ORDER BY name"
    ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def update_recurring_expense(expense_id: int, name: str, amount: float, category: str,
                             description: str, frequency: str, day_of_month: int,
                             start_date: str | None = None):
    conn = get_connection()
    conn.execute(
        """UPDATE recurring_expenses
           SET name = ?, amount = ?, category = ?, description = ?,
               frequency = ?, day_of_month = ?, start_date = ?
           WHERE id = ?""",
        (name, round(amount, 2), category, description, frequency, day_of_month, start_date, expense_id),
    )
    _sync_write(conn)


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
    """Auto-add due recurring expenses with correct scheduled dates."""
    from datetime import timedelta
    today = date.today()
    recurring = get_recurring_expenses(active_only=True)

    for rec in recurring:
        last_added = rec["last_added_date"]
        if last_added:
            last_dt = datetime.strptime(last_added, "%Y-%m-%d").date()
        else:
            last_dt = None

        desc = (f"[Recurring] {rec['name']}"
                + (f" — {rec['description']}" if rec["description"] else ""))

        if rec["frequency"] == "monthly":
            dom = rec["day_of_month"]
            # Determine starting month to check
            if last_dt:
                # Start checking from the month after last_added
                check_year, check_month = last_dt.year, last_dt.month
                check_month += 1
                if check_month > 12:
                    check_month = 1
                    check_year += 1
            else:
                # Never added — start from current month
                check_year, check_month = today.year, today.month

            # Add expenses for each missed month up to today
            while date(check_year, check_month, min(dom, 28)) <= today:
                import calendar as _cal
                actual_day = min(dom, _cal.monthrange(check_year, check_month)[1])
                expense_date = date(check_year, check_month, actual_day)
                if expense_date <= today:
                    add_expense(expense_date, rec["amount"], rec["category"], desc, rec["added_by"])
                    update_recurring_last_added(rec["id"], expense_date.isoformat())
                check_month += 1
                if check_month > 12:
                    check_month = 1
                    check_year += 1

        elif rec["frequency"] in ("weekly", "biweekly"):
            step = 7 if rec["frequency"] == "weekly" else 14
            # Determine anchor date
            if last_dt:
                cursor = last_dt + timedelta(days=step)
            elif rec.get("start_date"):
                cursor = datetime.strptime(rec["start_date"], "%Y-%m-%d").date()
            else:
                # Fallback: use created_at or today
                cursor = today

            # Add expenses for each missed scheduled date up to today
            while cursor <= today:
                add_expense(cursor, rec["amount"], rec["category"], desc, rec["added_by"])
                update_recurring_last_added(rec["id"], cursor.isoformat())
                cursor += timedelta(days=step)
