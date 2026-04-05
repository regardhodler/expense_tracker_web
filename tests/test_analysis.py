"""Tests for analysis.py — period dates, category summary, daily totals."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from analysis import get_period_dates, category_summary, daily_totals_for_month, rows_to_dataframe, love_points, DISPLAY_NAMES, aggregate_jueds_month, _person_badge, _person_label


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


# ---------------------------------------------------------------------------
# love_points
# ---------------------------------------------------------------------------

class TestLovePoints:
    """Tests for the input-based love points system."""

    def _make_rows(self, husband_manual=0, wife_manual=0, husband_recurring=0, wife_recurring=0):
        """Helper to build a DataFrame of expense rows."""
        rows = []
        for i in range(husband_manual):
            rows.append({"id": len(rows), "date": "2026-03-05", "amount": 10.0,
                         "category": "Food", "description": f"manual {i}", "added_by": "husband"})
        for i in range(wife_manual):
            rows.append({"id": len(rows), "date": "2026-03-05", "amount": 10.0,
                         "category": "Food", "description": f"manual {i}", "added_by": "wife"})
        for i in range(husband_recurring):
            rows.append({"id": len(rows), "date": "2026-03-01", "amount": 50.0,
                         "category": "Housing", "description": f"[Recurring] rent {i}", "added_by": "husband"})
        for i in range(wife_recurring):
            rows.append({"id": len(rows), "date": "2026-03-01", "amount": 50.0,
                         "category": "Housing", "description": f"[Recurring] sub {i}", "added_by": "wife"})
        return rows_to_dataframe(rows)

    def test_empty_df(self):
        df = rows_to_dataframe([])
        result = love_points(df)
        assert result["combined_points"] == 0
        assert result["tier"] == "warming_up"
        assert result["emoji"] == "❄️"
        assert isinstance(result["message"], str)
        assert result["points"]["husband"] == 0
        assert result["points"]["wife"] == 0

    def test_manual_entries_count_as_1_point(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result = love_points(df)
        assert result["points"]["husband"] == 3.0
        assert result["points"]["wife"] == 2.0
        assert result["combined_points"] == 5.0

    def test_recurring_entries_count_as_quarter_point(self):
        df = self._make_rows(husband_recurring=4)
        result = love_points(df)
        assert result["points"]["husband"] == 1.0  # 4 * 0.25
        assert result["combined_points"] == 1.0

    def test_mixed_manual_and_recurring(self):
        df = self._make_rows(husband_manual=2, wife_manual=1, husband_recurring=4, wife_recurring=2)
        result = love_points(df)
        # husband: 2 + (4*0.25) = 3.0, wife: 1 + (2*0.25) = 1.5
        assert result["points"]["husband"] == 3.0
        assert result["points"]["wife"] == 1.5
        assert result["combined_points"] == 4.5

    def test_tier_warming_up(self):
        df = self._make_rows(husband_manual=1)
        result = love_points(df)
        assert result["tier"] == "warming_up"
        assert result["emoji"] == "❄️"

    def test_tier_sweet(self):
        df = self._make_rows(husband_manual=2, wife_manual=1)
        result = love_points(df)
        assert result["tier"] == "sweet"
        assert result["emoji"] == "🥰"

    def test_tier_crushing(self):
        df = self._make_rows(husband_manual=3, wife_manual=3)
        result = love_points(df)
        assert result["tier"] == "crushing"
        assert result["emoji"] == "😍"

    def test_tier_lovey_dovey(self):
        df = self._make_rows(husband_manual=5, wife_manual=4)
        result = love_points(df)
        assert result["tier"] == "lovey_dovey"
        assert result["emoji"] == "💕"

    def test_tier_madly(self):
        df = self._make_rows(husband_manual=6, wife_manual=6)
        result = love_points(df)
        assert result["tier"] == "madly"
        assert result["emoji"] == "🔥"

    def test_tier_on_fire(self):
        df = self._make_rows(husband_manual=8, wife_manual=7)
        result = love_points(df)
        assert result["tier"] == "on_fire"
        assert result["emoji"] == "💘"

    def test_tier_inseparable(self):
        df = self._make_rows(husband_manual=9, wife_manual=9)
        result = love_points(df)
        assert result["tier"] == "inseparable"
        assert result["emoji"] == "🫂"

    def test_tier_power_couple(self):
        df = self._make_rows(husband_manual=11, wife_manual=10)
        result = love_points(df)
        assert result["tier"] == "power_couple"
        assert result["emoji"] == "👑"

    def test_tier_soulmates(self):
        df = self._make_rows(husband_manual=13, wife_manual=12)
        result = love_points(df)
        assert result["tier"] == "soulmates"
        assert result["emoji"] == "💪"

    def test_tier_soulmates_at_25(self):
        df = self._make_rows(husband_manual=13, wife_manual=12)
        result = love_points(df)
        assert result["tier"] == "soulmates"

    def test_tier_easter_egg(self):
        df = self._make_rows(husband_manual=14, wife_manual=12)
        result = love_points(df)
        assert result["tier"] == "easter_egg"
        assert result["emoji"] == "🌟"

    def test_message_is_deterministic_for_same_month(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result1 = love_points(df, year=2026, month=3)
        result2 = love_points(df, year=2026, month=3)
        assert result1["message"] == result2["message"]

    def test_message_changes_across_months(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result_mar = love_points(df, year=2026, month=3)
        result_apr = love_points(df, year=2026, month=4)
        assert isinstance(result_mar["message"], str)
        assert isinstance(result_apr["message"], str)

    def test_only_one_user(self):
        df = self._make_rows(husband_manual=5)
        result = love_points(df)
        assert result["points"]["husband"] == 5.0
        assert result["points"]["wife"] == 0
        assert result["combined_points"] == 5.0


# ---------------------------------------------------------------------------
# aggregate_jueds_month
# ---------------------------------------------------------------------------

class TestAggregateJuedsMonth:
    def _expense_rows(self):
        """Mixed rows: Jude recurring, Jude manual, wife manual."""
        return [
            {"id": 1, "date": "2026-01-05", "amount": 2000.0,
             "category": "Housing", "description": "[Recurring] Rent",
             "added_by": "husband", "is_tax_writeoff": 0},
            {"id": 2, "date": "2026-01-10", "amount": 500.0,
             "category": "Food", "description": "Groceries",
             "added_by": "husband", "is_tax_writeoff": 0},
            {"id": 3, "date": "2026-01-12", "amount": 300.0,
             "category": "Food", "description": "Lunch",
             "added_by": "wife", "is_tax_writeoff": 0},
            {"id": 4, "date": "2026-01-15", "amount": 100.0,
             "category": "Personal", "description": None,
             "added_by": "husband", "is_tax_writeoff": 0},
        ]

    def _income_rows(self):
        return [
            {"id": 1, "year": 2026, "month": 1, "amount": 3200.0,
             "label": "1st paycheck", "created_at": "2026-01-10"},
            {"id": 2, "year": 2026, "month": 1, "amount": 3200.0,
             "label": "2nd paycheck", "created_at": "2026-01-25"},
        ]

    def test_recurring_expense_is_correct(self):
        result = aggregate_jueds_month(self._expense_rows(), self._income_rows())
        assert result["recurring_expense"] == 2000.0

    def test_manual_expense_is_correct(self):
        result = aggregate_jueds_month(self._expense_rows(), self._income_rows())
        # 500 + 100 = 600 (wife's 300 excluded)
        assert result["manual_expense"] == 600.0

    def test_net_income_is_sum_of_income_rows(self):
        result = aggregate_jueds_month(self._expense_rows(), self._income_rows())
        assert result["net_income"] == 6400.0

    def test_free_cash_flow(self):
        result = aggregate_jueds_month(self._expense_rows(), self._income_rows())
        # 6400 - 2000 - 600 = 3800
        assert result["free_cash_flow"] == pytest.approx(3800.0)

    def test_no_income_returns_zero_net_income(self):
        result = aggregate_jueds_month(self._expense_rows(), [])
        assert result["net_income"] == 0.0

    def test_no_income_free_cash_flow_is_negative(self):
        result = aggregate_jueds_month(self._expense_rows(), [])
        assert result["free_cash_flow"] == pytest.approx(-2600.0)

    def test_empty_expenses_zero_totals(self):
        result = aggregate_jueds_month([], self._income_rows())
        assert result["recurring_expense"] == 0.0
        assert result["manual_expense"] == 0.0
        assert result["free_cash_flow"] == 6400.0

    def test_none_description_treated_as_manual(self):
        rows = [{"id": 1, "date": "2026-01-01", "amount": 100.0,
                 "category": "Food", "description": None,
                 "added_by": "husband", "is_tax_writeoff": 0}]
        result = aggregate_jueds_month(rows, [])
        assert result["manual_expense"] == 100.0
        assert result["recurring_expense"] == 0.0

    def test_wife_expenses_excluded(self):
        rows = [{"id": 1, "date": "2026-01-01", "amount": 500.0,
                 "category": "Food", "description": "wife groceries",
                 "added_by": "wife", "is_tax_writeoff": 0}]
        result = aggregate_jueds_month(rows, [])
        assert result["recurring_expense"] == 0.0


# ---------------------------------------------------------------------------
# _person_badge / _person_label
# ---------------------------------------------------------------------------

class TestPersonHelpers:
    def test_badge_husband_contains_jude(self):
        assert "Jude" in _person_badge("husband")

    def test_badge_husband_contains_blue_heart(self):
        assert "💙" in _person_badge("husband")

    def test_badge_husband_contains_blue_color(self):
        assert "#3498db" in _person_badge("husband")

    def test_badge_wife_contains_wincyl(self):
        assert "Wincyl" in _person_badge("wife")

    def test_badge_wife_contains_pink_heart(self):
        assert "🩷" in _person_badge("wife")

    def test_badge_wife_contains_pink_color(self):
        assert "#e056a0" in _person_badge("wife")

    def test_badge_unknown_returns_raw(self):
        assert _person_badge("unknown") == "unknown"

    def test_label_husband(self):
        assert _person_label("husband") == "💙 Jude"

    def test_label_wife(self):
        assert _person_label("wife") == "🩷 Wincyl"

    def test_label_unknown_returns_raw(self):
        assert _person_label("unknown") == "unknown"
