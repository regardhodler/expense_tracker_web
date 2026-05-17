# Jude's Quantitative Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Jude's Quantitative" page that shows Jude's recurring + manual expenses per month alongside logged income, displaying Free Cash Flow per month for any selected year.

**Architecture:** New `jude_income` table in the existing Turso DB stores paychecks; a pure aggregation helper in `analysis.py` computes per-month breakdowns from pre-fetched rows (keeping it unit-testable); a Plotly chart in `visualization.py` renders the 12-month view; the Streamlit page function in `app.py` wires everything together.

**Tech Stack:** Python 3.9+, Streamlit, Plotly (`plotly.graph_objects`), pandas, libsql_experimental (Turso), pytest

**Spec:** `docs/superpowers/specs/2026-04-05-jueds-quantitative-design.md`

---

## Chunk 1: DB Layer

### Task 1: Add `jude_income` table + CRUD to `database.py`

**Files:**
- Modify: `database.py`

Read `database.py` fully before editing. Find the `init_db()` function and the pattern used by other `add_*` / `get_*` / `delete_*` functions (e.g., `add_recurring_expense`, `get_recurring_expenses`, `deactivate_recurring_expense`). Follow those patterns exactly.

- [ ] **Step 1: Add table creation inside `init_db()`**

Locate the block in `init_db()` where other `CREATE TABLE IF NOT EXISTS` statements live. Add this table after the existing ones:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS jude_income (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        year       INTEGER NOT NULL,
        month      INTEGER NOT NULL,
        amount     REAL    NOT NULL,
        label      TEXT,
        created_at TEXT    NOT NULL
    )
""")
```

- [ ] **Step 2: Add module-level column list and `add_jude_income()`**

Near the top of `database.py` where `_COLUMNS`, `_GOAL_COLUMNS`, etc. are defined, add:

```python
_INCOME_COLUMNS = ["id", "year", "month", "amount", "label", "created_at"]
```

Then place this function near the other `add_*` functions. Note: use `_sync_write(conn)` (not `conn.commit()`) — this is the Turso pattern that commits AND syncs to the remote replica:

```python
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
```

- [ ] **Step 3: Add `get_jude_income()`**

Note: call `_sync_read(conn)` before the query — this syncs from the remote Turso replica so the caller sees the latest data:

```python
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
```

- [ ] **Step 4: Add `delete_jude_income()`**

Note: use `_sync_write(conn)` (not `conn.commit()`):

```python
def delete_jude_income(income_id: int) -> None:
    """Delete a single income entry by id."""
    conn = get_connection()
    conn.execute("DELETE FROM jude_income WHERE id = ?", (income_id,))
    _sync_write(conn)
```

- [ ] **Step 5: Commit**

```bash
git add database.py
git commit -m "feat: add jude_income table and CRUD functions"
```

---

## Chunk 2: Aggregation Logic

### Task 2: Add pure aggregation helper to `analysis.py`

**Files:**
- Modify: `analysis.py`
- Test: `tests/test_analysis.py`

This helper is pure (no DB calls) so it can be unit-tested. It takes pre-fetched expense rows and income rows and computes one month's breakdown.

- [ ] **Step 1: Write the failing tests**

Add this class to `tests/test_analysis.py`. First, add `aggregate_jueds_month` to the **existing** import line at the top of the file (do NOT add a second import statement):

```python
# Existing line — update it to include aggregate_jueds_month:
from analysis import get_period_dates, category_summary, daily_totals_for_month, rows_to_dataframe, love_points, DISPLAY_NAMES, aggregate_jueds_month
```

Then add the test class at the bottom of the file:

```python
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
        assert result["manual_expense"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_analysis.py::TestAggregateJuedsMonth -v
```

Expected: `ImportError` or `AttributeError` — `aggregate_jueds_month` does not exist yet.

- [ ] **Step 3: Implement `aggregate_jueds_month` in `analysis.py`**

Add this function near the bottom of `analysis.py`, after existing helpers:

```python
def aggregate_jueds_month(
    expense_rows: list[dict],
    income_rows: list[dict],
) -> dict:
    """
    Compute Jude's (husband) financial breakdown for a single month.

    Parameters
    ----------
    expense_rows : rows from get_expenses_between() for the target month
    income_rows  : rows from get_jude_income() filtered to the target month

    Returns
    -------
    dict with keys:
        recurring_expense  – sum of Jude's [Recurring] expenses
        manual_expense     – sum of Jude's non-recurring expenses
        net_income         – sum of income_rows amounts
        free_cash_flow     – net_income - recurring_expense - manual_expense
    """
    df = rows_to_dataframe(expense_rows)

    if df.empty:
        recurring_expense = 0.0
        manual_expense = 0.0
    else:
        jude_df = df[df["added_by"] == "husband"].copy()
        jude_df["description"] = jude_df["description"].fillna("")
        is_recurring = jude_df["description"].str.startswith("[Recurring]")
        recurring_expense = float(jude_df[is_recurring]["amount"].sum())
        manual_expense = float(jude_df[~is_recurring]["amount"].sum())

    net_income = sum(r["amount"] for r in income_rows)
    free_cash_flow = net_income - recurring_expense - manual_expense

    return {
        "recurring_expense": round(recurring_expense, 2),
        "manual_expense": round(manual_expense, 2),
        "net_income": round(net_income, 2),
        "free_cash_flow": round(free_cash_flow, 2),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_analysis.py::TestAggregateJuedsMonth -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add analysis.py tests/test_analysis.py
git commit -m "feat: add aggregate_jueds_month helper with tests"
```

---

## Chunk 3: Chart

### Task 3: Add `jueds_monthly_chart` to `visualization.py`

**Files:**
- Modify: `visualization.py`

Read `visualization.py` first and find the `yearly_mom_chart` function — use it as a reference for how bar+line combo charts are built and how per-point marker colors are set.

- [ ] **Step 1: Add the chart function**

Add after the existing chart functions:

```python
def jueds_monthly_chart(monthly_data: list[dict]) -> go.Figure:
    """
    Grouped bar chart (Net Income / Recurring Expense / Manual Expense)
    with a Free Cash Flow line overlay, colored green/red per point by sign.

    Parameters
    ----------
    monthly_data : list of 12 dicts, each with keys:
        month_label        – str, e.g. "Jan"
        net_income         – float
        recurring_expense  – float
        manual_expense     – float
        free_cash_flow     – float
    """
    labels = [d["month_label"] for d in monthly_data]
    net_income = [d["net_income"] for d in monthly_data]
    recurring = [d["recurring_expense"] for d in monthly_data]
    manual = [d["manual_expense"] for d in monthly_data]
    fcf = [d["free_cash_flow"] for d in monthly_data]
    fcf_colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in fcf]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Net Income",
        x=labels,
        y=net_income,
        marker_color="#3498db",
        opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        name="Recurring Expense",
        x=labels,
        y=recurring,
        marker_color="#e67e22",
        opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        name="Manual Expense",
        x=labels,
        y=manual,
        marker_color="#e74c3c",
        opacity=0.85,
    ))
    fig.add_trace(go.Scatter(
        name="Free Cash Flow",
        x=labels,
        y=fcf,
        mode="lines+markers",
        line=dict(color="#888888", width=2),
        marker=dict(color=fcf_colors, size=8),
        yaxis="y",
    ))

    fig.update_layout(
        barmode="group",
        xaxis_title="Month",
        yaxis_title="Amount",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
    )

    return fig
```

- [ ] **Step 2: Verify the chart renders without error (manual smoke test)**

```bash
python -c "
from visualization import jueds_monthly_chart
import calendar

data = []
for m in range(1, 13):
    data.append({
        'month_label': calendar.month_abbr[m],
        'net_income': 6400.0 if m <= 4 else 0.0,
        'recurring_expense': 2000.0,
        'manual_expense': 500.0,
        'free_cash_flow': 3900.0 if m <= 4 else -2500.0,
    })
fig = jueds_monthly_chart(data)
print('OK — traces:', len(fig.data))
"
```

Expected output: `OK — traces: 4`

- [ ] **Step 3: Commit**

```bash
git add visualization.py
git commit -m "feat: add jueds_monthly_chart to visualization"
```

---

## Chunk 4: Page Function

### Task 4: Add `page_jueds_quantitative` to `app.py` and register in sidebar

**Files:**
- Modify: `app.py`

Read the existing page functions (e.g., `page_dashboard`, `page_monthly_view`) to understand the Streamlit patterns used: `st.header`, `st.columns`, `st.selectbox`, `st.number_input`, `st.button`, `st.expander`, `st.plotly_chart`. The two-step delete confirmation pattern (button → session state key → confirm/cancel pair) is used in the income log below — `calendar` and `pandas` are already imported at module level in `app.py` as `calendar` and `pd`, so do NOT re-import them inside the function.

- [ ] **Step 1: Add the page function**

Add this function before the `if __name__ == "__main__":` block (or near the other page functions). Place it after `page_savings_goals`:

```python
def page_jueds_quantitative(username: str) -> None:
    """Jude's personal income vs expense dashboard."""
    st.header("Jude's Quantitative")

    # ── Year selector ──────────────────────────────────────────────────────
    current_year = date.today().year
    year_options = list(range(current_year, current_year - 5, -1))
    selected_year = st.selectbox("Year", year_options, index=0)

    # ── Income log section ─────────────────────────────────────────────────
    with st.expander("Log Income", expanded=True):
        col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
        with col1:
            month_names = [calendar.month_name[m] for m in range(1, 13)]
            income_month = st.selectbox(
                "Month", month_names,
                index=date.today().month - 1,
                key="income_month_select",
            )
            income_month_num = month_names.index(income_month) + 1
        with col2:
            income_amount = st.number_input(
                "Amount", min_value=0.01, step=100.0, format="%.2f",
                key="income_amount_input",
            )
        with col3:
            income_label = st.text_input(
                "Label (optional)", placeholder="e.g. 1st paycheck",
                key="income_label_input",
            )
        with col4:
            st.write("")  # vertical alignment spacer
            st.write("")
            if st.button("Add", key="add_income_btn", use_container_width=True):
                if income_amount > 0:
                    add_jude_income(selected_year, income_month_num, income_amount, income_label or None)
                    st.success("Income logged.")
                    st.rerun()

        # Show existing entries for the selected month
        all_income = get_jude_income(selected_year)
        month_income = [r for r in all_income if r["month"] == income_month_num]
        if month_income:
            st.markdown(f"**{income_month} entries**")
            for entry in month_income:
                ec1, ec2, ec3 = st.columns([3, 2, 1])
                with ec1:
                    st.write(entry["label"] or "—")
                with ec2:
                    st.write(f"${entry['amount']:,.2f}")
                with ec3:
                    confirm_key = f"confirm_delete_income_{entry['id']}"
                    if st.session_state.get(confirm_key):
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            if st.button("Yes, delete", key=f"yes_{entry['id']}",
                                         use_container_width=True):
                                delete_jude_income(entry["id"])
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                        with dc2:
                            if st.button("Cancel", key=f"cancel_{entry['id']}",
                                         use_container_width=True):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                    else:
                        if st.button("Delete", key=f"del_{entry['id']}",
                                     use_container_width=True):
                            st.session_state[confirm_key] = True
                            st.rerun()
        else:
            st.caption(f"No income entries for {income_month} {selected_year}.")

    # ── Build 12-month data ────────────────────────────────────────────────
    all_income_year = get_jude_income(selected_year)
    monthly_rows = []

    for m in range(1, 13):
        m_start = date(selected_year, m, 1)
        m_end = date(selected_year, m, calendar.monthrange(selected_year, m)[1])
        expense_rows = get_expenses_between(m_start, m_end)
        month_income_rows = [r for r in all_income_year if r["month"] == m]

        agg = aggregate_jueds_month(expense_rows, month_income_rows)
        has_income = len(month_income_rows) > 0

        monthly_rows.append({
            "month_label": calendar.month_abbr[m],
            "month_num": m,
            "net_income": agg["net_income"],
            "recurring_expense": agg["recurring_expense"],
            "manual_expense": agg["manual_expense"],
            "free_cash_flow": agg["free_cash_flow"],
            "has_income": has_income,
        })

    # ── Chart ──────────────────────────────────────────────────────────────
    st.plotly_chart(jueds_monthly_chart(monthly_rows), use_container_width=True)

    # ── Monthly breakdown table ────────────────────────────────────────────
    st.subheader("Monthly Breakdown")

    def _fcf_style(val: float, has_income: bool) -> str:
        if not has_income:
            return "—"
        sign = "+" if val >= 0 else ""
        return f"{sign}${val:,.2f}"

    def _income_display(val: float, has_income: bool) -> str:
        return f"${val:,.2f}" if has_income else "—"

    table_rows = []
    for r in monthly_rows:
        table_rows.append({
            "Month": r["month_label"],
            "Net Income": _income_display(r["net_income"], r["has_income"]),
            "Recurring Expense": f"${r['recurring_expense']:,.2f}",
            "Manual Expense": f"${r['manual_expense']:,.2f}",
            "Free Cash Flow": _fcf_style(r["free_cash_flow"], r["has_income"]),
            "_fcf_raw": r["free_cash_flow"],
            "_has_income": r["has_income"],
        })

    display_df = pd.DataFrame(table_rows).drop(columns=["_fcf_raw", "_has_income"])

    def highlight_fcf(row):
        styles = [""] * len(row)
        col_idx = list(row.index).index("Free Cash Flow")
        # Use get_loc to safely convert index label to positional index
        pos = display_df.index.get_loc(row.name)
        raw_val = table_rows[pos]["_fcf_raw"]
        has = table_rows[pos]["_has_income"]
        if has:
            if raw_val >= 0:
                styles[col_idx] = "color: #27ae60; background-color: #eafaf1"
            else:
                styles[col_idx] = "color: #c0392b; background-color: #fdedec"
        return styles

    st.dataframe(
        display_df.style.apply(highlight_fcf, axis=1),
        use_container_width=True,
        hide_index=True,
    )
```

- [ ] **Step 2: Add imports used by the page function**

At the top of the function `page_jueds_quantitative` the following functions are called — verify they are already imported at the module level of `app.py`. Add any that are missing:

- `add_jude_income` — from database.py (add to the `from database import ...` line)
- `get_jude_income` — from database.py
- `delete_jude_income` — from database.py
- `aggregate_jueds_month` — from analysis.py (add to the `from analysis import ...` line)
- `jueds_monthly_chart` — from visualization.py (add to the `from visualization import ...` line)

- [ ] **Step 3: Register in sidebar**

Find the `st.sidebar.radio(...)` call with the page list. Add `"Jude's Quantitative"` to the list:

```python
# Before:
["Dashboard", "Add Expense", "Monthly View", "Analysis",
 "Search", "Budgets", "Recurring Expense", "Manage Expenses", "Savings Goals"]

# After:
["Dashboard", "Add Expense", "Monthly View", "Analysis",
 "Search", "Budgets", "Recurring Expense", "Manage Expenses", "Savings Goals",
 "Jude's Quantitative"]
```

Then add the mapping in the `pages` dict:

```python
"Jude's Quantitative": page_jueds_quantitative,
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass (the page function itself is not unit-tested, following existing codebase convention).

- [ ] **Step 5: Smoke-test manually**

Run the app:

```bash
streamlit run app.py
```

Verify:
1. "Jude's Quantitative" appears in the sidebar
2. Navigate to the page — it loads without error
3. Log 2 income entries for the current month — they appear in the log
4. Delete one entry using the two-step confirm — it disappears
5. Switch year — table and chart update
6. FCF cell is green for positive months, red for negative months
7. Net Income shows `—` for months with no income entries

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add Jude's Quantitative page with income log and FCF breakdown"
```
