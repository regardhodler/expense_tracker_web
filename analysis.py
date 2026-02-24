"""Period filtering, summaries, and category analysis."""

import calendar
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

CATEGORIES = [
    "Housing", "Food", "Health", "Transportation",
    "Personal", "Entertainment", "Others",
]

PERIOD_OPTIONS = [
    "Current month",
    "Specific month/year",
    "YTD",
    "Last 1 year",
    "Last 2 years",
    "Last 3 years",
]


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["id", "date", "amount", "category", "description", "added_by"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_period_dates(period: str, month: int | None = None, year: int | None = None) -> tuple[date, date]:
    today = date.today()
    if period == "Current month":
        return today.replace(day=1), today
    elif period == "Specific month/year" and month and year:
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, min(end, today) if end > today else end
    elif period == "YTD":
        return date(today.year, 1, 1), today
    elif period == "Last 1 year":
        return today - relativedelta(years=1), today
    elif period == "Last 2 years":
        return today - relativedelta(years=2), today
    elif period == "Last 3 years":
        return today - relativedelta(years=3), today
    return today.replace(day=1), today


def category_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if df.empty:
        return pd.DataFrame(columns=["Category", "Amount", "% of Total"]), 0.0
    summary = df.groupby("category")["amount"].sum().reset_index()
    summary.columns = ["Category", "Amount"]
    total = summary["Amount"].sum()
    summary["% of Total"] = (summary["Amount"] / total * 100).round(1) if total > 0 else 0.0
    summary = summary.sort_values("Amount", ascending=False).reset_index(drop=True)
    return summary, total


def daily_totals_for_month(df: pd.DataFrame, year: int, month: int) -> dict[int, float]:
    """Return {day_number: total_spent} for a given month."""
    if df.empty:
        return {}
    mask = (df["date"].dt.year == year) & (df["date"].dt.month == month)
    monthly = df[mask]
    if monthly.empty:
        return {}
    return monthly.groupby(monthly["date"].dt.day)["amount"].sum().to_dict()


def expenses_for_day(df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    """Return expenses for a specific day."""
    if df.empty:
        return df
    mask = df["date"].dt.date == target_date
    return df[mask]
