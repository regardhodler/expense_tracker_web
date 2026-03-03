"""Tests for analysis.py — period dates, category summary, daily totals."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from analysis import get_period_dates, category_summary, daily_totals_for_month, rows_to_dataframe


# ---------------------------------------------------------------------------
# rows_to_dataframe
# ---------------------------------------------------------------------------

class TestRowsToDataframe:
    def test_empty_list(self):
        df = rows_to_dataframe([])
        assert df.empty
        assert "date" in df.columns

    def test_converts_dates(self):
        rows = [{"id": 1, "date": "2025-03-15", "amount": 10.0,
                 "category": "Food", "description": "", "added_by": "test"}]
        df = rows_to_dataframe(rows)
        assert pd.api.types.is_datetime64_any_dtype(df["date"])


# ---------------------------------------------------------------------------
# get_period_dates
# ---------------------------------------------------------------------------

class TestGetPeriodDates:
    @patch("analysis.date")
    def test_current_month(self, mock_date):
        mock_date.today.return_value = date(2025, 6, 15)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        start, end = get_period_dates("Current month")
        assert start == date(2025, 6, 1)
        assert end == date(2025, 6, 15)

    def test_specific_month(self):
        start, end = get_period_dates("Specific month/year", month=2, year=2024)
        assert start == date(2024, 2, 1)
        assert end.day == 29  # 2024 is a leap year

    def test_ytd(self):
        start, end = get_period_dates("YTD")
        assert start.month == 1
        assert start.day == 1
        assert start.year == date.today().year

    def test_last_1_year(self):
        start, end = get_period_dates("Last 1 year")
        diff = (end - start).days
        assert 364 <= diff <= 366

    def test_unknown_period_defaults(self):
        start, end = get_period_dates("nonsense")
        assert start.day == 1  # defaults to current month start


# ---------------------------------------------------------------------------
# category_summary
# ---------------------------------------------------------------------------

class TestCategorySummary:
    def test_empty_df(self):
        df = pd.DataFrame(columns=["category", "amount"])
        summary, total = category_summary(df)
        assert total == 0.0
        assert summary.empty

    def test_single_category(self):
        df = pd.DataFrame({"category": ["Food", "Food"], "amount": [10.0, 20.0]})
        summary, total = category_summary(df)
        assert total == 30.0
        assert len(summary) == 1
        assert summary.iloc[0]["% of Total"] == 100.0

    def test_multiple_categories_sorted(self):
        df = pd.DataFrame({
            "category": ["Food", "Health", "Food", "Health", "Entertainment"],
            "amount": [10.0, 50.0, 30.0, 20.0, 5.0],
        })
        summary, total = category_summary(df)
        assert total == 115.0
        # Should be sorted descending by amount
        assert summary.iloc[0]["Category"] == "Health"
        assert summary.iloc[0]["Amount"] == 70.0


# ---------------------------------------------------------------------------
# daily_totals_for_month
# ---------------------------------------------------------------------------

class TestDailyTotals:
    def test_empty_df(self):
        df = pd.DataFrame(columns=["date", "amount"])
        result = daily_totals_for_month(df, 2025, 3)
        assert result == {}

    def test_correct_totals(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-03-01", "2025-03-01", "2025-03-15"]),
            "amount": [10.0, 20.0, 5.0],
        })
        result = daily_totals_for_month(df, 2025, 3)
        assert result[1] == 30.0
        assert result[15] == 5.0
        assert 2 not in result

    def test_wrong_month_ignored(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-03-01", "2025-04-01"]),
            "amount": [10.0, 20.0],
        })
        result = daily_totals_for_month(df, 2025, 3)
        assert 1 in result
        assert len(result) == 1
