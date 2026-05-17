# MoM Love Points Bug Fix — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the month-over-month love points calculation so it only compares fully completed months, not the current in-progress month.

**Architecture:** One-file change in `app.py` (`page_analysis`). The `_down_months` loop upper bound changes from `range(1, 12)` to `range(1, today.month)`, and `_yr_end` is capped at today for the current year. No schema changes, no new dependencies.

**Tech Stack:** Python, Streamlit, pandas, datetime

---

## Chunk 1: Bug Fix

**Files:**
- Modify: `analysis.py` (add `count_down_months` helper at bottom of file)
- Modify: `app.py` (lines ~924–956, call helper instead of inline logic)
- Modify: `tests/test_analysis.py` (add regression test against the real helper)

---

### Task 1: Add testable helper to `analysis.py`

**Files:**
- Modify: `analysis.py`

- [ ] **Step 1: Add `count_down_months` at the bottom of `analysis.py` (after all existing functions)**

```python
def count_down_months(monthly_totals: dict, up_to_month: int) -> int:
    """Count months with lower spending than the prior month, for completed months only.

    Args:
        monthly_totals: dict mapping month number (1-12) to total spending float.
        up_to_month: current month number (1-12). Only months strictly before this
                     are considered complete. E.g. if today is May, pass 5 — months
                     1-4 are complete, month 5 is in progress and excluded.

    Returns:
        Number of completed month pairs where spending decreased.
        Returns 0 if up_to_month <= 1 (no complete pairs yet).
    """
    vals = [monthly_totals.get(m, 0) for m in range(1, 13)]
    return sum(
        1 for i in range(1, up_to_month)
        if vals[i] > 0 and vals[i - 1] > 0 and vals[i] < vals[i - 1]
    )
```

---

### Task 2: Write failing test against the real helper

**Files:**
- Modify: `tests/test_analysis.py`

- [ ] **Step 1: Add these tests at the bottom of `tests/test_analysis.py`**

```python
from analysis import count_down_months


def test_count_down_months_excludes_current_month():
    # Every month lower than the prior — all pairs are "down"
    # Jan=1200, Feb=1100, Mar=1000, Apr=900, May=800, ...
    monthly = {m: (13 - m) * 100.0 for m in range(1, 13)}

    # up_to_month=5 (May) → only pairs (Jan→Feb), (Feb→Mar), (Mar→Apr) counted = 3
    assert count_down_months(monthly, up_to_month=5) == 3

    # up_to_month=3 (March) → only pair (Jan→Feb) = 1
    assert count_down_months(monthly, up_to_month=3) == 1

    # up_to_month=1 (January) → range(1,1) is empty → 0
    assert count_down_months(monthly, up_to_month=1) == 0

    # up_to_month=2 (February) → range(1,2) = [1] → one pair (Jan→Feb) = 1
    assert count_down_months(monthly, up_to_month=2) == 1


def test_count_down_months_skips_zero_months():
    # Months with 0 spending should not count as "down"
    monthly = {1: 1000.0, 2: 0.0, 3: 800.0}
    # Pair (1→2): vals[1]=0 → skipped. Pair (2→3): vals[1]=0 → skipped.
    assert count_down_months(monthly, up_to_month=4) == 0


def test_count_down_months_up_month():
    # Spending goes up every month — no down months
    monthly = {m: m * 100.0 for m in range(1, 13)}
    assert count_down_months(monthly, up_to_month=12) == 0
```

- [ ] **Step 2: Run tests to verify they FAIL (function doesn't exist yet)**

```
pytest tests/test_analysis.py::test_count_down_months_excludes_current_month -v
```

Expected: `ImportError` or `FAILED` — `count_down_months` not yet defined.

---

### Task 3: Verify helper passes tests

- [ ] **Step 1: Run all three new tests**

```
pytest tests/test_analysis.py::test_count_down_months_excludes_current_month tests/test_analysis.py::test_count_down_months_skips_zero_months tests/test_analysis.py::test_count_down_months_up_month -v
```

Expected: all 3 PASS.

---

### Task 4: Update `app.py` to use the helper

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `count_down_months` to the import from `analysis` at the top of `app.py`**

Find the existing import block (around line 22–27) that imports from `analysis`:
```python
from analysis import (
    CATEGORIES, PERIOD_OPTIONS, rows_to_dataframe,
    ...
)
```
Add `count_down_months` to that import list.

- [ ] **Step 2: Find `_yr_end` in `page_analysis` (around line 931)**

Change:
```python
_yr_end = date(_year_sel, 12, 31)
```
To:
```python
_yr_end = min(date(_year_sel, 12, 31), _today) if _year_sel == _today.year else date(_year_sel, 12, 31)
```

> `_today` is defined just above as `_today = date.today()`.

- [ ] **Step 3: Find the `_down_months` block (around line 950) and replace**

Old:
```python
_mom_vals = [_monthly.get(m, 0) for m in range(1, 13)]
_down_months = sum(
    1 for i in range(1, 12)
    if _mom_vals[i] > 0 and _mom_vals[i - 1] > 0 and _mom_vals[i] < _mom_vals[i - 1]
)
```

New:
```python
_down_months = count_down_months(_monthly, up_to_month=_today.month)
```

---

### Task 5: Verify and commit

- [ ] **Step 1: Run the regression test — expect PASS**

```
pytest tests/test_analysis.py::test_down_months_excludes_current_partial_month -v
```

Expected output:
```
PASSED tests/test_analysis.py::test_down_months_excludes_current_partial_month
```

- [ ] **Step 2: Run the full test suite — expect no regressions**

```
pytest tests/ -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 3: Manual smoke test**

Start the app (`streamlit run app.py`), navigate to Analysis & Reports, check the MoM green banner. It should now show only completed months. In May 2026, the maximum it can report is 3 down-months (Jan→Feb, Feb→Mar, Mar→Apr).

- [ ] **Step 4: Commit**

```bash
git add app.py tests/test_analysis.py
git commit -m "fix(analysis): exclude current partial month from MoM love points count"
```
