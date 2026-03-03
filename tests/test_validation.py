"""Tests for validation.py — all validation edge cases."""

from datetime import date

import pytest

from validation import validate_expense, MAX_AMOUNT, MAX_DESCRIPTION_LENGTH


class TestAmountValidation:
    def test_zero_amount(self):
        ok, msg = validate_expense(0, "Food", "")
        assert not ok
        assert "positive" in msg

    def test_negative_amount(self):
        ok, msg = validate_expense(-5.0, "Food", "")
        assert not ok

    def test_exceeds_max(self):
        ok, msg = validate_expense(MAX_AMOUNT + 1, "Food", "")
        assert not ok
        assert "exceed" in msg

    def test_max_amount_exact(self):
        ok, _ = validate_expense(MAX_AMOUNT, "Food", "")
        assert ok

    def test_valid_amount(self):
        ok, _ = validate_expense(42.50, "Food", "lunch")
        assert ok


class TestDescriptionValidation:
    def test_too_long(self):
        ok, msg = validate_expense(10.0, "Food", "x" * (MAX_DESCRIPTION_LENGTH + 1))
        assert not ok
        assert "500" in msg

    def test_max_length_exact(self):
        ok, _ = validate_expense(10.0, "Food", "x" * MAX_DESCRIPTION_LENGTH)
        assert ok

    def test_others_requires_description(self):
        ok, msg = validate_expense(10.0, "Others", "")
        assert not ok
        assert "required" in msg.lower()

    def test_others_whitespace_only(self):
        ok, msg = validate_expense(10.0, "Others", "   ")
        assert not ok

    def test_others_with_description(self):
        ok, _ = validate_expense(10.0, "Others", "gift for friend")
        assert ok


class TestDuplicateDetection:
    def _make_rows(self, amt=25.0, cat="Food", dt="2025-03-01"):
        return [{"date": dt, "amount": amt, "category": cat, "description": "", "added_by": "test"}]

    def test_duplicate_detected(self):
        rows = self._make_rows()
        ok, msg = validate_expense(
            25.0, "Food", "", existing_expenses=rows, exp_date=date(2025, 3, 1),
        )
        assert not ok
        assert msg.startswith("DUPLICATE:")

    def test_duplicate_confirmed(self):
        rows = self._make_rows()
        ok, _ = validate_expense(
            25.0, "Food", "", existing_expenses=rows, exp_date=date(2025, 3, 1),
            confirm_duplicate=True,
        )
        assert ok

    def test_different_amount_no_duplicate(self):
        rows = self._make_rows(amt=25.0)
        ok, _ = validate_expense(
            30.0, "Food", "", existing_expenses=rows, exp_date=date(2025, 3, 1),
        )
        assert ok

    def test_different_category_no_duplicate(self):
        rows = self._make_rows(cat="Health")
        ok, _ = validate_expense(
            25.0, "Food", "", existing_expenses=rows, exp_date=date(2025, 3, 1),
        )
        assert ok

    def test_different_date_no_duplicate(self):
        rows = self._make_rows(dt="2025-03-02")
        ok, _ = validate_expense(
            25.0, "Food", "", existing_expenses=rows, exp_date=date(2025, 3, 1),
        )
        assert ok

    def test_no_existing_expenses(self):
        ok, _ = validate_expense(25.0, "Food", "", existing_expenses=None, exp_date=date(2025, 3, 1))
        assert ok

    def test_empty_existing_expenses(self):
        ok, _ = validate_expense(25.0, "Food", "", existing_expenses=[], exp_date=date(2025, 3, 1))
        assert ok
