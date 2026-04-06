"""Turso (libsql) CRUD operations for the expense tracker.

Uses a single cached connection to avoid the overhead of connecting and
syncing on every call.  The local replica is stored in a temp directory
so the path is stable on Streamlit Cloud.
"""

import tempfile
import os
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import libsql_experimental as libsql
import streamlit as st

logger = logging.getLogger(__name__)

_COLUMNS = ["id", "date", "amount", "category", "description", "added_by", "is_tax_writeoff"]
_INCOME_COLUMNS = ["id", "year", "month", "amount", "label", "created_at"]

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
            added_by TEXT DEFAULT 'unknown',
            is_tax_writeoff INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL UNIQUE,
            monthly_limit REAL NOT NULL,
            notes TEXT DEFAULT '',
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

    # Migration: add is_tax_writeoff column for existing rows
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN is_tax_writeoff INTEGER DEFAULT 0")
    except Exception:
        pass  # column already exists

    # Indexes for recurring expense lookups
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date_desc_added ON expenses(date, description, added_by)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_expenses(active)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL NOT NULL DEFAULT 0,
            category TEXT,
            emoji TEXT DEFAULT '🎯',
            created_by TEXT DEFAULT 'unknown',
            created_at TEXT DEFAULT (datetime('now')),
            completed INTEGER DEFAULT 0,
            completed_at TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS date_nights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            night_date TEXT NOT NULL UNIQUE,
            where_text TEXT,
            how_text TEXT,
            expense_amount REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Migration: add expense_amount to existing rows
    try:
        conn.execute("ALTER TABLE date_nights ADD COLUMN expense_amount REAL DEFAULT 0")
    except Exception:
        pass  # column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jude_income (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            amount     REAL    NOT NULL,
            label      TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    _sync_write(conn)


# ---------------------------------------------------------------------------
# Expense CRUD
# ---------------------------------------------------------------------------

def add_expense(date_val: date, amount: float, category: str, description: str, added_by: str, is_tax_writeoff: bool = False):
    conn = get_connection()
    conn.execute(
        "INSERT INTO expenses (date, amount, category, description, added_by, is_tax_writeoff) VALUES (?, ?, ?, ?, ?, ?)",
        (date_val.isoformat(), round(amount, 2), category, description, added_by, int(is_tax_writeoff)),
    )
    _sync_write(conn)


def get_expense_by_id(expense_id: int) -> Optional[dict]:
    """Fetch a single expense by ID."""
    conn = get_connection()
    _sync_read(conn)
    row = conn.execute(
        "SELECT id, date, amount, category, description, added_by, is_tax_writeoff "
        "FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(_COLUMNS, row))


def update_expense(expense_id: int, date_val: date, amount: float, category: str, description: str,
                   is_tax_writeoff: bool = False, added_by: Optional[str] = None):
    """Update an existing expense."""
    conn = get_connection()
    if added_by is not None:
        conn.execute(
            "UPDATE expenses SET date = ?, amount = ?, category = ?, description = ?, is_tax_writeoff = ?, added_by = ? WHERE id = ?",
            (date_val.isoformat(), round(amount, 2), category, description, int(is_tax_writeoff), added_by, expense_id),
        )
    else:
        conn.execute(
            "UPDATE expenses SET date = ?, amount = ?, category = ?, description = ?, is_tax_writeoff = ? WHERE id = ?",
            (date_val.isoformat(), round(amount, 2), category, description, int(is_tax_writeoff), expense_id),
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
        "SELECT id, date, amount, category, description, added_by, is_tax_writeoff "
        "FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return _rows_to_dicts(rows)


def get_recent_expenses(limit: int = 10) -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by, is_tax_writeoff "
        "FROM expenses ORDER BY date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return _rows_to_dicts(rows)


def get_tax_writeoffs(start_date: date, end_date: date) -> list[dict]:
    """Return all tax write-off expenses in a date range."""
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        "SELECT id, date, amount, category, description, added_by, is_tax_writeoff "
        "FROM expenses WHERE is_tax_writeoff = 1 AND date >= ? AND date <= ? ORDER BY date DESC, id DESC",
        (start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    return _rows_to_dicts(rows)


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------

def get_budgets() -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    # Add notes column if it doesn't exist (migration for existing DBs)
    try:
        conn.execute("ALTER TABLE budgets ADD COLUMN notes TEXT DEFAULT ''")
        _sync_write(conn)
    except Exception:
        pass
    rows = conn.execute(
        "SELECT category, monthly_limit, notes, updated_by, updated_at FROM budgets ORDER BY category"
    ).fetchall()
    return [dict(zip(["category", "monthly_limit", "notes", "updated_by", "updated_at"], r)) for r in rows]


def set_budget(category: str, monthly_limit: float, updated_by: str, notes: str = ""):
    conn = get_connection()
    conn.execute(
        """INSERT INTO budgets (category, monthly_limit, notes, updated_by, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(category) DO UPDATE SET
               monthly_limit = excluded.monthly_limit,
               notes = excluded.notes,
               updated_by = excluded.updated_by,
               updated_at = datetime('now')""",
        (category, round(monthly_limit, 2), notes.strip(), updated_by),
    )
    _sync_write(conn)


def delete_budget(category: str):
    conn = get_connection()
    conn.execute("DELETE FROM budgets WHERE category = ?", (category,))
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
                          start_date: Optional[str] = None):
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
                             start_date: Optional[str] = None, added_by: Optional[str] = None):
    conn = get_connection()
    if added_by is not None:
        conn.execute(
            """UPDATE recurring_expenses
               SET name = ?, amount = ?, category = ?, description = ?,
                   frequency = ?, day_of_month = ?, start_date = ?, added_by = ?
               WHERE id = ?""",
            (name, round(amount, 2), category, description, frequency, day_of_month, start_date, added_by, expense_id),
        )
    else:
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
    # Get the recurring expense details to build the description pattern
    rec = conn.execute(
        "SELECT name, description, added_by FROM recurring_expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.execute("UPDATE recurring_expenses SET active = 0 WHERE id = ?", (expense_id,))
    # Delete future materialized entries for this recurring expense
    if rec:
        name, desc, added_by = rec
        full_desc = f"[Recurring] {name}" + (f" — {desc}" if desc else "")
        tomorrow = date.today() + timedelta(days=1)
        conn.execute(
            "DELETE FROM expenses WHERE description = ? AND added_by = ? AND date >= ?",
            (full_desc, added_by, tomorrow.isoformat()),
        )
    _sync_write(conn)


def update_recurring_last_added(expense_id: int, last_date: str):
    conn = get_connection()
    conn.execute(
        "UPDATE recurring_expenses SET last_added_date = ? WHERE id = ?",
        (last_date, expense_id),
    )
    _sync_write(conn)


def _recurring_entry_exists(expense_date: date, description: str, added_by: str) -> bool:
    """Check if a recurring expense entry already exists for a given date."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM expenses WHERE date = ? AND description = ? AND added_by = ? LIMIT 1",
        (expense_date.isoformat(), description, added_by),
    ).fetchone()
    return row is not None


def process_recurring_expenses():
    """Auto-add due recurring expenses with correct scheduled dates.

    Batches all inserts into a single transaction and skips dates that
    have already been processed (using last_added_date) to avoid
    redundant DB calls on every app load.
    """
    import calendar as _cal
    from datetime import timedelta

    today = date.today()
    # Project 3 months into the future
    fwd_month = today.month + 3
    fwd_year = today.year + (fwd_month - 1) // 12
    fwd_month = (fwd_month - 1) % 12 + 1
    forward_limit = date(fwd_year, fwd_month, min(today.day, 28))

    conn = get_connection()
    recurring = get_recurring_expenses(active_only=True)

    # Collect all inserts so we can batch them in one transaction
    inserts: list[tuple] = []  # (date, amount, category, description, added_by)
    last_added_updates: dict[int, str] = {}  # rec_id -> last_date_iso

    for rec in recurring:
        last_added = rec["last_added_date"]
        if last_added:
            last_dt = datetime.strptime(last_added, "%Y-%m-%d").date()
        else:
            last_dt = None

        desc = (f"[Recurring] {rec['name']}"
                + (f" — {rec['description']}" if rec["description"] else ""))

        jan1 = date(today.year, 1, 1)

        if rec["frequency"] == "monthly":
            dom = rec["day_of_month"]
            # Start from the month after last_added_date if it's >= Jan of current year
            if last_dt and last_dt >= jan1:
                start_month = last_dt.month + 1
                start_year = last_dt.year
                if start_month > 12:
                    start_month = 1
                    start_year += 1
            else:
                start_year, start_month = today.year, 1

            check_year, check_month = start_year, start_month
            while date(check_year, check_month, min(dom, 28)) <= forward_limit:
                actual_day = min(dom, _cal.monthrange(check_year, check_month)[1])
                expense_date = date(check_year, check_month, actual_day)
                if expense_date <= forward_limit:
                    if not _recurring_entry_exists(expense_date, desc, rec["added_by"]):
                        inserts.append((expense_date.isoformat(), rec["amount"],
                                        rec["category"], desc, rec["added_by"]))
                    last_added_updates[rec["id"]] = expense_date.isoformat()
                check_month += 1
                if check_month > 12:
                    check_month = 1
                    check_year += 1

        elif rec["frequency"] in ("weekly", "biweekly"):
            step = 7 if rec["frequency"] == "weekly" else 14
            if rec.get("start_date"):
                anchor = datetime.strptime(rec["start_date"], "%Y-%m-%d").date()
                if anchor < jan1:
                    days_diff = (jan1 - anchor).days
                    remainder = days_diff % step
                    cursor = jan1 if remainder == 0 else jan1 + timedelta(days=step - remainder)
                else:
                    cursor = anchor
            else:
                cursor = jan1

            # Skip past already-processed dates
            if last_dt and last_dt >= jan1:
                while cursor <= last_dt:
                    cursor += timedelta(days=step)

            while cursor <= forward_limit:
                if not _recurring_entry_exists(cursor, desc, rec["added_by"]):
                    inserts.append((cursor.isoformat(), rec["amount"],
                                    rec["category"], desc, rec["added_by"]))
                last_added_updates[rec["id"]] = cursor.isoformat()
                cursor += timedelta(days=step)

    # Batch write: all inserts + last_added updates in one transaction
    if inserts or last_added_updates:
        conn.executemany(
            "INSERT INTO expenses (date, amount, category, description, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            inserts,
        )
        for rec_id, last_date in last_added_updates.items():
            conn.execute(
                "UPDATE recurring_expenses SET last_added_date = ? WHERE id = ?",
                (last_date, rec_id),
            )
        _sync_write(conn)


# ---------------------------------------------------------------------------
# Savings Goals CRUD
# ---------------------------------------------------------------------------

_GOAL_COLUMNS = ["id", "name", "target_amount", "current_amount", "category",
                  "emoji", "created_by", "created_at", "completed", "completed_at"]


def get_savings_goals() -> list[dict]:
    conn = get_connection()
    _sync_read(conn)
    rows = conn.execute(
        f"SELECT {', '.join(_GOAL_COLUMNS)} FROM savings_goals ORDER BY completed ASC, created_at DESC"
    ).fetchall()
    return [dict(zip(_GOAL_COLUMNS, r)) for r in rows]


def add_savings_goal(name: str, target_amount: float, category: Optional[str], emoji: str, created_by: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO savings_goals (name, target_amount, category, emoji, created_by) VALUES (?, ?, ?, ?, ?)",
        (name, round(target_amount, 2), category, emoji, created_by),
    )
    _sync_write(conn)


def update_savings_goal_progress(goal_id: int, current_amount: float):
    conn = get_connection()
    conn.execute(
        "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
        (round(current_amount, 2), goal_id),
    )
    _sync_write(conn)


def complete_savings_goal(goal_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE savings_goals SET completed = 1, completed_at = datetime('now') WHERE id = ?",
        (goal_id,),
    )
    _sync_write(conn)


def delete_savings_goal(goal_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
    _sync_write(conn)


# ---------------------------------------------------------------------------
# Date Nights CRUD
# ---------------------------------------------------------------------------

_DATE_NIGHT_COLUMNS = ["id", "night_date", "where_text", "how_text", "expense_amount", "created_at"]


def add_date_night(night_date: date, where_text: str, how_text: str, expense_amount: float = 0.0):
    """Record a date night. Upserts so re-tagging the same date updates it."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO date_nights (night_date, where_text, how_text, expense_amount)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(night_date) DO UPDATE SET where_text=excluded.where_text, how_text=excluded.how_text, expense_amount=excluded.expense_amount""",
        (night_date.isoformat(), where_text.strip(), how_text.strip(), round(expense_amount, 2)),
    )
    _sync_write(conn)


def get_date_nights(start_date: Optional[date] = None, end_date: Optional[date] = None) -> list[dict]:
    """Return date nights ordered newest first, optionally filtered by date range."""
    conn = get_connection()
    _sync_read(conn)
    if start_date and end_date:
        rows = conn.execute(
            f"SELECT {', '.join(_DATE_NIGHT_COLUMNS)} FROM date_nights "
            "WHERE night_date >= ? AND night_date <= ? ORDER BY night_date DESC",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {', '.join(_DATE_NIGHT_COLUMNS)} FROM date_nights ORDER BY night_date DESC"
        ).fetchall()
    return [dict(zip(_DATE_NIGHT_COLUMNS, r)) for r in rows]


def get_date_night_dates(year: int, month: int) -> set[int]:
    """Return the set of day-numbers that are marked as date nights for a given month."""
    conn = get_connection()
    _sync_read(conn)
    month_str = f"{year}-{month:02d}"
    rows = conn.execute(
        "SELECT night_date FROM date_nights WHERE night_date LIKE ?",
        (f"{month_str}-%",),
    ).fetchall()
    return {int(r[0].split("-")[2]) for r in rows}


def delete_date_night(night_date: date):
    conn = get_connection()
    conn.execute("DELETE FROM date_nights WHERE night_date = ?", (night_date.isoformat(),))
    _sync_write(conn)


# ---------------------------------------------------------------------------
# Jude Income CRUD
# ---------------------------------------------------------------------------

def add_jude_income(year: int, month: int, amount: float, label: Optional[str] = None) -> None:
    """Insert a new income entry for Jude."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO jude_income (year, month, amount, label, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (year, month, round(amount, 2), label),
    )
    _sync_write(conn)


def get_jude_income(year: int) -> list[dict]:
    """Return all income entries for the given year, ordered by month then created_at."""
    conn = get_connection()
    _sync_read(conn)
    cursor = conn.execute(
        "SELECT id, year, month, amount, label, created_at FROM jude_income WHERE year = ? ORDER BY month, created_at",
        (year,),
    )
    rows = cursor.fetchall()
    return [dict(zip(_INCOME_COLUMNS, row)) for row in rows]


def delete_jude_income(income_id: int) -> None:
    """Delete a single income entry by id."""
    conn = get_connection()
    conn.execute("DELETE FROM jude_income WHERE id = ?", (income_id,))
    _sync_write(conn)
