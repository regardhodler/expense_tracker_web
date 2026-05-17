# "Who Is This For?" Badges Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the "Who is this for?" form defaults so they use the logged-in user, and add colored 💙/🩷 badges to all expense displays across the app.

**Architecture:** Two pure helper functions (`_person_badge`, `_person_label`) go into `analysis.py` for testability, then are imported in `app.py`. All UI changes are in `app.py` only — form default fixes (2 forms) and badge rendering in 7 page locations.

**Tech Stack:** Python 3.9+, Streamlit, pandas, pytest

**Spec:** `docs/superpowers/specs/2026-04-05-who-is-this-for-badges-design.md`

---

## Chunk 1: Helper Functions

### Task 1: Add `_person_badge` and `_person_label` to `analysis.py` with tests

**Files:**
- Modify: `analysis.py`
- Modify: `tests/test_analysis.py`

Read `analysis.py` fully before editing. Add the two helpers at the bottom of the file after `aggregate_jueds_month`.

- [ ] **Step 1: Write failing tests**

Add `_person_badge, _person_label` to the existing import line at the top of `tests/test_analysis.py`:

```python
from analysis import get_period_dates, category_summary, daily_totals_for_month, rows_to_dataframe, love_points, DISPLAY_NAMES, aggregate_jueds_month, _person_badge, _person_label
```

Add this class at the bottom of `tests/test_analysis.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/test_analysis.py::TestPersonHelpers -v 2>&1 | head -15
```

Expected: ImportError — `_person_badge` not found.

- [ ] **Step 3: Add helpers to `analysis.py`**

Add at the bottom of `analysis.py`, after `aggregate_jueds_month`:

```python
def _person_badge(added_by: str) -> str:
    """HTML pill badge — use with unsafe_allow_html=True in Streamlit."""
    if added_by == "husband":
        return (
            '<span style="background:#3498db;color:white;padding:1px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600">💙 Jude</span>'
        )
    elif added_by == "wife":
        return (
            '<span style="background:#e056a0;color:white;padding:1px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600">🩷 Wincyl</span>'
        )
    return added_by


def _person_label(added_by: str) -> str:
    """Plain-text emoji label for dataframe cells (no HTML rendering)."""
    return {"husband": "💙 Jude", "wife": "🩷 Wincyl"}.get(added_by, added_by)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/test_analysis.py::TestPersonHelpers -v
```

Expected: 10 tests, all PASS.

- [ ] **Step 5: Add imports to `app.py`**

Find the `from analysis import (` block at line 22. Add `_person_badge` and `_person_label` to the existing import list.

- [ ] **Step 6: Run full test suite**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add analysis.py tests/test_analysis.py app.py
git commit -m "feat: add _person_badge and _person_label helpers"
```

---

## Chunk 2: Form Default Fixes

### Task 2: Fix "Who is this for?" defaults on Add Expense and Recurring Expense forms

**Files:**
- Modify: `app.py`

Read `page_add_expense` and `page_recurring` before editing. The `username` parameter is always `"husband"` or `"wife"`. `DISPLAY_NAMES` maps `"husband" → "Jude"` and `"wife" → "Wincyl"` — it is already imported.

- [ ] **Step 1: Fix Add Expense form default (line ~695)**

Find this line in `page_add_expense`:
```python
added_for = st.selectbox("Who is this for?", ["Jude", "Wincyl"], key="add_expense_for")
```

Replace with:
```python
_person_options = ["Jude", "Wincyl"]
_default_for = DISPLAY_NAMES.get(username, "Jude")
added_for = st.selectbox(
    "Who is this for?",
    _person_options,
    index=_person_options.index(_default_for) if _default_for in _person_options else 0,
    key="add_expense_for",
)
```

- [ ] **Step 2: Fix Recurring Expense add form default (line ~1226)**

Find this line in `page_recurring`:
```python
added_for = st.selectbox("Who is this for?", ["Jude", "Wincyl"], key="recurring_expense_for")
```

Replace with:
```python
_person_options = ["Jude", "Wincyl"]
_default_for = DISPLAY_NAMES.get(username, "Jude")
added_for = st.selectbox(
    "Who is this for?",
    _person_options,
    index=_person_options.index(_default_for) if _default_for in _person_options else 0,
    key="recurring_expense_for",
)
```

Note: The **Edit** form in `page_recurring` (around line 1172) already defaults to the saved record value — do NOT change it.

- [ ] **Step 3: Run full test suite**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "fix: default 'Who is this for?' to logged-in user on Add Expense and Recurring forms"
```

---

## Chunk 3: Badge Integration — Primary Pages

### Task 3: Add badges to Recurring Expense list, Add Expense recent list, and Monthly View

**Files:**
- Modify: `app.py`

Read each page function fully before editing.

- [ ] **Step 1: Recurring Expense list — add badge next to name**

In `page_recurring`, find the expense list loop (around line 1267). The name/amount display looks like:
```python
st.markdown(f"**{rec['name']}** — ${rec['amount']:,.2f} / {rec['frequency']}{schedule_info}  \n...")
```

Prepend the badge:
```python
st.markdown(
    f"{_person_badge(rec['added_by'])} &nbsp; **{rec['name']}** — ${rec['amount']:,.2f} / {rec['frequency']}{schedule_info}  \n...",
    unsafe_allow_html=True,
)
```

Make sure `unsafe_allow_html=True` is set on this `st.markdown` call.

- [ ] **Step 2: Add Expense — recent expenses dataframe**

In `page_add_expense`, find around line 667-668:
```python
df_display = df[["date", "amount", "category", "description", "added_by"]].copy()
df_display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
```

Change to:
```python
df_display = df[["date", "amount", "category", "description", "added_by"]].copy()
df_display["added_by"] = df_display["added_by"].map(_person_label)
df_display.columns = ["Date", "Amount", "Category", "Description", "Who is this for?"]
```

- [ ] **Step 3: Monthly View — calendar cell badge**

In `page_monthly_view`, find the calendar HTML block (around line 844-848):
```python
html += (
    f'<div title="{tooltip}" style="color:{color};white-space:nowrap;overflow:hidden;'
    f'text-overflow:ellipsis;font-size:0.75em;line-height:1.4;cursor:default">'
    f'{icon}${amt:,.0f} {cat}</div>'
)
```

Add the badge after the category/amount on the same line:
```python
_badge = _person_badge(exp.get("added_by", ""))
html += (
    f'<div title="{tooltip}" style="color:{color};white-space:nowrap;overflow:hidden;'
    f'text-overflow:ellipsis;font-size:0.75em;line-height:1.4;cursor:default">'
    f'{icon}${amt:,.0f} {cat} {_badge}</div>'
)
```

Read the surrounding loop carefully to confirm the variable names (`exp`, `amt`, `cat`, `icon`, `tooltip`, `color`) before editing.

- [ ] **Step 4: Monthly View — Day Details caption**

Find line 886:
```python
st.caption(f"Added by: {exp['added_by']}")
```

Replace with:
```python
st.markdown(f"For: {_person_badge(exp['added_by'])}", unsafe_allow_html=True)
```

- [ ] **Step 5: Monthly View — "All expenses this month" dataframe**

Find line 914-916:
```python
display = df[["date", "amount", "category", "description", "added_by"]].copy()
display["date"] = display["date"].dt.strftime("%Y-%m-%d")
display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
```

Change to:
```python
display = df[["date", "amount", "category", "description", "added_by"]].copy()
display["date"] = display["date"].dt.strftime("%Y-%m-%d")
display["added_by"] = display["added_by"].map(_person_label)
display.columns = ["Date", "Amount", "Category", "Description", "Who is this for?"]
```

- [ ] **Step 6: Run full test suite**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat: add person badges to Recurring Expense list, Add Expense, and Monthly View"
```

---

## Chunk 4: Badge Consistency Pass

### Task 4: Add badges to Dashboard, Analysis, Search, and Manage Expenses

**Files:**
- Modify: `app.py`

Same pattern for every location: map `added_by` through `_person_label`, rename column from `"Added By"` to `"Who is this for?"`. Read each section before editing.

- [ ] **Step 1: Dashboard — per-category drill-down (current month, line ~614)**

Find:
```python
_cur_cat_df.columns = ["Date", "Amount", "Description", "Added By"]
```

Before that line, add:
```python
_cur_cat_df["added_by"] = _cur_cat_df["added_by"].map(_person_label)
```

Then change the columns line to:
```python
_cur_cat_df.columns = ["Date", "Amount", "Description", "Who is this for?"]
```

- [ ] **Step 2: Dashboard — per-category drill-down (previous month, line ~625)**

Same pattern for `_prev_cat_df`:
```python
_prev_cat_df["added_by"] = _prev_cat_df["added_by"].map(_person_label)
_prev_cat_df.columns = ["Date", "Amount", "Description", "Who is this for?"]
```

- [ ] **Step 3: Dashboard — recent expenses list (line ~668)**

Find:
```python
df_display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
```

Before it, add:
```python
df_display["added_by"] = df_display["added_by"].map(_person_label)
```

Then rename:
```python
df_display.columns = ["Date", "Amount", "Category", "Description", "Who is this for?"]
```

- [ ] **Step 4: Analysis — per-category drill-down (line ~1036)**

Find:
```python
_cat_display.columns = ["Date", "Amount", "Description", "Added By"]
```

Before it, add:
```python
_cat_display["added_by"] = _cat_display["added_by"].map(_person_label)
```

Then rename:
```python
_cat_display.columns = ["Date", "Amount", "Description", "Who is this for?"]
```

- [ ] **Step 5: Search — results dataframe (line ~1350)**

Find:
```python
display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
```

Before it, add:
```python
display["added_by"] = display["added_by"].map(_person_label)
```

Then rename:
```python
display.columns = ["Date", "Amount", "Category", "Description", "Who is this for?"]
```

- [ ] **Step 6: Manage Expenses — CSV export dataframe (line ~1495)**

This location already has an existing lambda map:
```python
df_export["added_by"] = df_export["added_by"].map(lambda x: DISPLAY_NAMES.get(x, x))
df_export.columns = ["Date", "Amount", "Category", "Description", "Added By"]
```

REPLACE both lines with:
```python
df_export["added_by"] = df_export["added_by"].map(_person_label)
df_export.columns = ["Date", "Amount", "Category", "Description", "Who is this for?"]
```

Do NOT add a second `.map()` call — replace the existing lambda entirely.

Note: `page_budgets` has no individual expense dataframe — **skip it**, no changes needed there.

- [ ] **Step 7: Run full test suite**

```bash
cd "C:\Users\16476\claude projects\expense_tracker_web" && python -m pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat: apply Who is this for? badges across Dashboard, Analysis, Search, Manage Expenses"
```
