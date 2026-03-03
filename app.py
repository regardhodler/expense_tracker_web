"""Expense Tracker — Streamlit app for couples to track shared expenses."""

import calendar
import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from database import (
    init_db, add_expense, delete_expense, get_expenses_between, get_recent_expenses,
    get_expense_by_id, update_expense,
    get_budgets, set_budget, get_monthly_category_totals,
    add_recurring_expense, get_recurring_expenses, deactivate_recurring_expense,
    update_recurring_expense, process_recurring_expenses,
)
from analysis import (
    CATEGORIES, PERIOD_OPTIONS, rows_to_dataframe,
    get_period_dates, category_summary, daily_totals_for_month,
    expenses_for_day, spending_projections, month_comparison,
)
from visualization import pie_chart, bar_chart, monthly_trend_chart, comparison_bar_chart
from validation import validate_expense, MAX_AMOUNT, MAX_DESCRIPTION_LENGTH

# ---------------------------------------------------------------------------
# PWA support
# ---------------------------------------------------------------------------

def inject_pwa():
    """Inject manifest, service-worker registration, and Apple PWA meta tags."""
    st.markdown(
        """
        <link rel="manifest" href="app/_statics/manifest.json">
        <link rel="apple-touch-icon" href="app/_statics/icon-192.png">
        <meta name="theme-color" content="#ff4b4b">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
        <meta name="apple-mobile-web-app-title" content="Expenses">
        <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('app/_statics/sw.js')
                .then(reg => console.log('SW registered:', reg.scope))
                .catch(err => console.warn('SW registration failed:', err));
        }
        </script>
        """,
        unsafe_allow_html=True,
    )


def inject_mobile_css():
    """Responsive CSS for mobile devices."""
    st.markdown("""
        <style>
        @media (max-width: 768px) {
            /* Compact calendar */
            table td, table th { height: 55px !important; font-size: 0.7em !important; padding: 2px 3px !important; }
            /* Smaller metrics */
            [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
            [data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
            [data-testid="stMetricDelta"] { font-size: 0.7rem !important; }
        }
        @media (max-width: 480px) {
            /* Further compress calendar */
            table td, table th { height: 40px !important; font-size: 0.6em !important; padding: 1px 2px !important; }
            /* Force columns to stack */
            [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
            [data-testid="stHorizontalBlock"] > div { flex: 100% !important; min-width: 100% !important; }
            /* Smaller metrics */
            [data-testid="stMetricValue"] { font-size: 1rem !important; }
        }
        </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Config & setup
# ---------------------------------------------------------------------------

def _get_secret(key: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then env vars, then default."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        import os
        return os.environ.get(key, default)

st.set_page_config(page_title="Expense Tracker", page_icon="$", layout="wide")


@st.cache_data(ttl=3600)
def _build_auth_config() -> dict:
    """Build authentication config in memory (no file I/O). Cached 1 hour."""
    pw_husband = _get_secret("HUSBAND_PASSWORD", "changeme123")
    pw_wife = _get_secret("WIFE_PASSWORD", "changeme123")
    cookie_key = _get_secret("COOKIE_KEY", "expense_tracker_secret_key_change_me")
    hashed = stauth.Hasher([pw_husband, pw_wife]).generate()
    return {
        "credentials": {
            "usernames": {
                "husband": {
                    "email": "husband@home.local",
                    "name": "Husband",
                    "password": hashed[0],
                },
                "wife": {
                    "email": "wife@home.local",
                    "name": "Wife",
                    "password": hashed[1],
                },
            }
        },
        "cookie": {
            "name": "expense_tracker_auth",
            "key": cookie_key,
            "expiry_days": 30,
        },
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def authenticate():
    config = _build_auth_config()

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    name, auth_status, username = authenticator.login(location="main")
    return authenticator, name, auth_status, username


# ---------------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------------

def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame to CSV bytes for download."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_dashboard(username: str):
    st.header("Dashboard")
    today = date.today()

    # Quick stats
    month_start = today.replace(day=1)
    year_start = date(today.year, 1, 1)
    month_rows = get_expenses_between(month_start, today)
    ytd_rows = get_expenses_between(year_start, today)
    month_total = sum(r["amount"] for r in month_rows)
    ytd_total = sum(r["amount"] for r in ytd_rows)

    # Previous month for comparison
    if today.month == 1:
        prev_month_start = date(today.year - 1, 12, 1)
        prev_month_end = date(today.year - 1, 12, 31)
    else:
        prev_month_start = date(today.year, today.month - 1, 1)
        prev_last_day = calendar.monthrange(today.year, today.month - 1)[1]
        prev_month_end = date(today.year, today.month - 1, prev_last_day)
    prev_month_rows = get_expenses_between(prev_month_start, prev_month_end)
    prev_month_total = sum(r["amount"] for r in prev_month_rows)

    month_delta = month_total - prev_month_total if prev_month_total > 0 else None

    col1, col2 = st.columns(2)
    col1.metric("This Month", f"${month_total:,.2f}",
                delta=f"${month_delta:,.2f}" if month_delta is not None else None,
                delta_color="inverse")
    col2.metric("Year to Date", f"${ytd_total:,.2f}")

    # Projections
    if month_rows:
        proj = spending_projections(month_rows, month_start, today)
        p1, p2, p3 = st.columns(3)
        p1.metric("Daily Average", f"${proj['daily_avg']:,.2f}")
        p2.metric("Weekly Average", f"${proj['weekly_avg']:,.2f}")
        p3.metric("Projected Month Total", f"${proj['projected_total']:,.2f}")
        st.caption(
            f"{proj['days_elapsed']} of {proj['days_in_month']} days into the month. "
            f"Averaging ${proj['daily_avg']:,.2f}/day, on track for "
            f"${proj['projected_total']:,.2f} this month."
        )

    # Month-over-Month comparison
    if month_rows or prev_month_rows:
        with st.expander("Month-over-Month Details"):
            comp_df, cur_t, prev_t = month_comparison(month_rows, prev_month_rows)
            if not comp_df.empty:
                display_comp = comp_df.copy()
                display_comp["Current"] = display_comp["Current"].map("${:,.2f}".format)
                display_comp["Previous"] = display_comp["Previous"].map("${:,.2f}".format)
                display_comp["Delta"] = comp_df["Delta"].map(
                    lambda x: f"+${x:,.2f}" if x >= 0 else f"-${abs(x):,.2f}"
                )
                display_comp["Delta%"] = comp_df["Delta%"].map(
                    lambda x: f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%"
                )
                st.dataframe(display_comp, use_container_width=True, hide_index=True)
                st.plotly_chart(comparison_bar_chart(comp_df), use_container_width=True)
            else:
                st.info("No data to compare.")

    # Over-budget warnings
    budgets = get_budgets()
    if budgets:
        category_totals = get_monthly_category_totals(today.year, today.month)
        for b in budgets:
            spent = category_totals.get(b["category"], 0)
            if spent > b["monthly_limit"]:
                over = spent - b["monthly_limit"]
                st.error(
                    f"**{b['category']}** is over budget! "
                    f"${spent:,.2f} / ${b['monthly_limit']:,.2f} "
                    f"(${over:,.2f} over)"
                )

    # Recent expenses
    st.subheader("Recent Expenses")
    recent = get_recent_expenses(10)
    if recent:
        df = pd.DataFrame(recent)
        df_display = df[["date", "amount", "category", "description", "added_by"]].copy()
        df_display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
        df_display["Amount"] = df_display["Amount"].map("${:,.2f}".format)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No expenses yet. Add your first one!")

    # Monthly trend (YTD)
    if ytd_rows:
        st.subheader("Monthly Trend (YTD)")
        df_ytd = rows_to_dataframe(ytd_rows)
        trend = monthly_trend_chart(df_ytd)
        if trend:
            st.plotly_chart(trend, use_container_width=True)


def page_add_expense(username: str):
    st.header("Add Expense")

    with st.form("add_expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            exp_date = st.date_input("Date", value=date.today())
        with col2:
            amount = st.number_input(
                "Amount ($)", min_value=0.01, max_value=MAX_AMOUNT, step=0.01, format="%.2f",
            )

        category = st.selectbox("Category", CATEGORIES)

        if category == "Others":
            description = st.text_input("Description (required for Others)", "", max_chars=MAX_DESCRIPTION_LENGTH)
        else:
            description = st.text_input("Description (optional)", "", max_chars=MAX_DESCRIPTION_LENGTH)

        submitted = st.form_submit_button("Add Expense", use_container_width=True)

        if submitted:
            # Check for duplicate (fetch today's expenses for comparison)
            day_expenses = get_expenses_between(exp_date, exp_date)
            confirm = st.session_state.get("_confirm_duplicate", False)

            valid, msg = validate_expense(
                amount, category, description.strip(),
                existing_expenses=day_expenses,
                exp_date=exp_date,
                confirm_duplicate=confirm,
            )

            if not valid:
                if msg.startswith("DUPLICATE:"):
                    st.warning(msg.replace("DUPLICATE: ", ""))
                    st.session_state["_confirm_duplicate"] = True
                else:
                    st.error(msg)
            else:
                add_expense(exp_date, amount, category, description.strip(), username)
                st.success(f"Added ${amount:,.2f} for {category} on {exp_date}!")
                st.session_state.pop("_confirm_duplicate", None)


def page_monthly_view(username: str):
    st.header("Monthly View")
    today = date.today()

    col1, col2 = st.columns(2)
    with col1:
        month = st.selectbox("Month", range(1, 13), index=today.month - 1,
                             format_func=lambda m: calendar.month_name[m])
    with col2:
        year = st.number_input("Year", min_value=2020, max_value=2100, value=today.year)

    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)
    rows = get_expenses_between(month_start, month_end)
    df = rows_to_dataframe(rows)

    # Calendar grid
    st.subheader(f"{calendar.month_name[month]} {year}")

    CATEGORY_COLORS = {
        "Housing": "#4CAF50",
        "Food": "#FF9800",
        "Health": "#E91E63",
        "Transportation": "#2196F3",
        "Personal": "#9C27B0",
        "Entertainment": "#00BCD4",
        "Others": "#607D8B",
    }

    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = cal.monthdayscalendar(year, month)

    TH_STYLE = "background:#1a1a2e;color:#ccc;padding:6px;text-align:center;border:1px solid #333;font-size:0.85em"
    TD_STYLE = "border:1px solid #333;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#0e1117"
    TD_TODAY = "border:2px solid #4a8cff;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#1a2744"
    TD_EMPTY = "border:1px solid #333;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#0a0a12"

    html = '<table style="width:100%;border-collapse:collapse;table-layout:fixed"><tr>'

    for day_name in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
        html += f'<th style="{TH_STYLE}">{day_name}</th>'
    html += "</tr>"

    for week in weeks:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += f'<td style="{TD_EMPTY}"></td>'
            else:
                current_date = date(year, month, day)
                is_today = current_date == today
                style = TD_TODAY if is_today else TD_STYLE
                day_expenses = expenses_for_day(df, current_date)

                html += f'<td style="{style}">'
                html += f'<div style="font-weight:bold;color:#e0e0e0;margin-bottom:3px;font-size:0.95em">{day}</div>'

                if not day_expenses.empty:
                    for _, exp in day_expenses.iterrows():
                        cat = exp["category"]
                        color = CATEGORY_COLORS.get(cat, "#999")
                        amt = exp["amount"]
                        html += (
                            f'<div style="color:{color};white-space:nowrap;overflow:hidden;'
                            f'text-overflow:ellipsis;font-size:0.75em;line-height:1.4">'
                            f"${amt:,.0f} {cat}</div>"
                        )
                    if len(day_expenses) > 1:
                        day_total = day_expenses["amount"].sum()
                        html += (
                            f'<div style="font-size:0.75em;color:#ff6b6b;margin-top:2px;'
                            f'font-weight:bold">${day_total:,.2f}</div>'
                        )

                html += "</td>"
        html += "</tr>"

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)

    # Category breakdown
    st.subheader("Category Breakdown")
    if df.empty:
        st.info("No expenses this month.")
    else:
        summary, total = category_summary(df)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.markdown(f"**Grand Total: ${total:,.2f}**")

    # CSV download for this month
    if not df.empty:
        csv_df = df[["date", "amount", "category", "description", "added_by"]].copy()
        csv_df["date"] = csv_df["date"].dt.strftime("%Y-%m-%d")
        csv_df.columns = ["Date", "Amount", "Category", "Description", "Added By"]
        st.download_button(
            "Download CSV",
            data=_df_to_csv_bytes(csv_df),
            file_name=f"expenses_{year}_{month:02d}.csv",
            mime="text/csv",
        )

    # Expense list for this month
    if not df.empty:
        with st.expander("All expenses this month"):
            display = df[["date", "amount", "category", "description", "added_by"]].copy()
            display["date"] = display["date"].dt.strftime("%Y-%m-%d")
            display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
            st.dataframe(display, use_container_width=True, hide_index=True)


def page_analysis(username: str):
    st.header("Analysis & Reports")

    period = st.selectbox("Period", PERIOD_OPTIONS)

    specific_month, specific_year = None, None
    if period == "Specific month/year":
        col1, col2 = st.columns(2)
        with col1:
            specific_month = st.selectbox("Month", range(1, 13),
                                          format_func=lambda m: calendar.month_name[m],
                                          key="analysis_month")
        with col2:
            specific_year = st.number_input("Year", min_value=2020, max_value=2100,
                                            value=date.today().year, key="analysis_year")

    start, end = get_period_dates(period, specific_month, specific_year)
    rows = get_expenses_between(start, end)
    df = rows_to_dataframe(rows)

    if df.empty:
        st.info(f"No expenses found for {period} ({start} to {end}).")
        return

    summary, total = category_summary(df)

    st.subheader(f"Total Spent: ${total:,.2f}")
    st.caption(f"Period: {start} to {end}")

    # CSV download for this period
    csv_df = df[["date", "amount", "category", "description", "added_by"]].copy()
    csv_df["date"] = csv_df["date"].dt.strftime("%Y-%m-%d")
    csv_df.columns = ["Date", "Amount", "Category", "Description", "Added By"]
    st.download_button(
        "Download CSV",
        data=_df_to_csv_bytes(csv_df),
        file_name=f"expenses_{start}_{end}.csv",
        mime="text/csv",
    )

    # Category table with warnings
    st.subheader("Per-Category Breakdown")
    display_summary = summary.copy()
    display_summary["Amount"] = display_summary["Amount"].map("${:,.2f}".format)
    display_summary["% of Total"] = display_summary["% of Total"].map("{:.1f}%".format)
    st.dataframe(display_summary, use_container_width=True, hide_index=True)

    # Warnings for high-percentage categories
    for _, row in summary.iterrows():
        pct = row["% of Total"]
        cat = row["Category"]
        if cat == "Food" and pct > 30:
            st.warning(f"Food spending is {pct:.1f}% of total (above 30% threshold)")
        elif cat == "Entertainment" and pct > 20:
            st.warning(f"Entertainment spending is {pct:.1f}% of total (above 20% threshold)")
        elif pct > 40:
            st.warning(f"{cat} spending is {pct:.1f}% of total (above 40% threshold)")

    # Charts
    st.subheader("Pie Chart")
    st.plotly_chart(pie_chart(summary), use_container_width=True)
    st.subheader("Bar Chart")
    st.plotly_chart(bar_chart(summary), use_container_width=True)

    # Monthly trend (if period spans multiple months)
    if (end - start).days > 31:
        st.subheader("Monthly Spending Trend")
        trend = monthly_trend_chart(df)
        if trend:
            st.plotly_chart(trend, use_container_width=True)


def page_budgets(username: str):
    st.header("Budget Tracking")

    # Set budgets
    st.subheader("Set Monthly Budgets")
    with st.form("budget_form"):
        category = st.selectbox("Category", CATEGORIES)
        limit = st.number_input("Monthly Limit ($)", min_value=0.01, max_value=MAX_AMOUNT, step=10.0, format="%.2f")
        if st.form_submit_button("Set Budget", use_container_width=True):
            set_budget(category, limit, username)
            st.success(f"Budget for {category} set to ${limit:,.2f}")

    # Show current budgets with progress
    st.subheader("Current Month Progress")
    today = date.today()
    budgets = get_budgets()

    if not budgets:
        st.info("No budgets set yet. Use the form above to set category limits.")
        return

    category_totals = get_monthly_category_totals(today.year, today.month)

    for b in budgets:
        cat = b["category"]
        limit_val = b["monthly_limit"]
        spent = category_totals.get(cat, 0)
        pct = min(spent / limit_val, 1.0) if limit_val > 0 else 0

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.progress(pct, text=f"{cat}")
        with col2:
            st.caption(f"${spent:,.2f} / ${limit_val:,.2f}")
        with col3:
            if spent > limit_val:
                st.error(f"Over by ${spent - limit_val:,.2f}")
            else:
                st.caption(f"${limit_val - spent:,.2f} left")


def page_recurring(username: str):
    st.header("Recurring Payments")

    # --- Edit form (shown when editing) ---
    editing_id = st.session_state.get("editing_recurring_id")
    if editing_id is not None:
        recurring_all = get_recurring_expenses(active_only=True)
        edit_rec = next((r for r in recurring_all if r["id"] == editing_id), None)
        if edit_rec:
            st.subheader(f"Edit: {edit_rec['name']}")
            with st.form("edit_recurring_form"):
                e_name = st.text_input("Name", value=edit_rec["name"], max_chars=100)
                col1, col2 = st.columns(2)
                with col1:
                    e_amount = st.number_input("Amount ($)", min_value=0.01, max_value=MAX_AMOUNT,
                                               step=0.01, format="%.2f", value=float(edit_rec["amount"]))
                with col2:
                    cat_idx = CATEGORIES.index(edit_rec["category"]) if edit_rec["category"] in CATEGORIES else 0
                    e_category = st.selectbox("Category", CATEGORIES, index=cat_idx)
                e_description = st.text_input("Description (optional)", value=edit_rec["description"] or "",
                                              max_chars=MAX_DESCRIPTION_LENGTH)
                col3, col4 = st.columns(2)
                freq_options = ["monthly", "weekly", "biweekly"]
                freq_idx = freq_options.index(edit_rec["frequency"]) if edit_rec["frequency"] in freq_options else 0
                with col3:
                    e_frequency = st.selectbox("Frequency", freq_options, index=freq_idx)
                with col4:
                    if e_frequency == "monthly":
                        e_day_of_month = st.number_input("Day of Month", min_value=1, max_value=28,
                                                         value=edit_rec["day_of_month"] or 1)
                        e_start_date = None
                    else:
                        existing_start = None
                        if edit_rec.get("start_date"):
                            from datetime import datetime as _dt
                            existing_start = _dt.strptime(edit_rec["start_date"], "%Y-%m-%d").date()
                        e_start_date_input = st.date_input("Start Date",
                                                           value=existing_start or date.today())
                        e_start_date = e_start_date_input.isoformat()
                        e_day_of_month = 1

                col_save, col_cancel = st.columns(2)
                with col_save:
                    save = st.form_submit_button("Save Changes", use_container_width=True)
                with col_cancel:
                    cancel = st.form_submit_button("Cancel", use_container_width=True)

                if save:
                    if not e_name.strip():
                        st.error("Name is required.")
                    else:
                        update_recurring_expense(
                            editing_id, e_name.strip(), e_amount, e_category,
                            e_description.strip(), e_frequency, e_day_of_month, e_start_date,
                        )
                        st.session_state.pop("editing_recurring_id", None)
                        st.session_state.pop("recurring_processed", None)
                        st.success("Recurring expense updated!")
                        st.rerun()
                if cancel:
                    st.session_state.pop("editing_recurring_id", None)
                    st.rerun()
            return  # Don't show the rest while editing

    # --- Add recurring ---
    st.subheader("Add Recurring Expense")
    with st.form("recurring_form", clear_on_submit=True):
        name = st.text_input("Name (e.g. Rent, Netflix)", max_chars=100)
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount ($)", min_value=0.01, max_value=MAX_AMOUNT, step=0.01, format="%.2f")
        with col2:
            category = st.selectbox("Category", CATEGORIES)
        description = st.text_input("Description (optional)", "", max_chars=MAX_DESCRIPTION_LENGTH)

        col3, col4 = st.columns(2)
        with col3:
            frequency = st.selectbox("Frequency", ["monthly", "weekly", "biweekly"])
        with col4:
            if frequency == "monthly":
                day_of_month = st.number_input("Day of Month", min_value=1, max_value=28, value=1)
                start_date = None
            else:
                start_date_input = st.date_input("Start Date", value=date.today())
                start_date = start_date_input.isoformat()
                day_of_month = 1

        if st.form_submit_button("Add Recurring Expense", use_container_width=True):
            if not name.strip():
                st.error("Name is required.")
            else:
                add_recurring_expense(
                    name.strip(), amount, category, description.strip(),
                    frequency, day_of_month, username, start_date,
                )
                st.session_state.pop("recurring_processed", None)
                st.success(f"Added recurring: {name} — ${amount:,.2f} ({frequency})")
                st.rerun()

    # --- List existing ---
    st.subheader("Active Recurring Expenses")
    recurring = get_recurring_expenses(active_only=True)

    if not recurring:
        st.info("No active recurring expenses.")
        return

    for rec in recurring:
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            schedule_info = ""
            if rec["frequency"] == "monthly":
                schedule_info = f" (day {rec['day_of_month']})"
            elif rec.get("start_date"):
                schedule_info = f" (from {rec['start_date']})"
            st.markdown(
                f"**{rec['name']}** — ${rec['amount']:,.2f} / {rec['frequency']}{schedule_info}  \n"
                f"Category: {rec['category']}"
                + (f" | {rec['description']}" if rec['description'] else "")
            )
        with col2:
            last = rec["last_added_date"] or "Never"
            st.caption(f"Last added: {last}")
        with col3:
            if st.button("Edit", key=f"edit_{rec['id']}"):
                st.session_state["editing_recurring_id"] = rec["id"]
                st.rerun()
        with col4:
            if st.button("Deactivate", key=f"deactivate_{rec['id']}"):
                deactivate_recurring_expense(rec["id"])
                st.rerun()


def page_search(username: str):
    st.header("Search & Filter")

    # Filters
    search_text = st.text_input("Search description", "", placeholder="e.g. groceries, rent...")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=date.today().replace(day=1), key="search_start")
    with col2:
        end = st.date_input("To", value=date.today(), key="search_end")

    col3, col4 = st.columns(2)
    with col3:
        selected_categories = st.multiselect("Categories", CATEGORIES, default=CATEGORIES)
    with col4:
        selected_users = st.multiselect("Added by", ["husband", "wife"], default=["husband", "wife"])

    col5, col6 = st.columns(2)
    with col5:
        min_amount = st.number_input("Min amount ($)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    with col6:
        max_amount = st.number_input("Max amount ($)", min_value=0.0, value=0.0, step=1.0, format="%.2f",
                                     help="Leave at 0 for no max limit")

    # Fetch and filter
    rows = get_expenses_between(start, end)
    df = rows_to_dataframe(rows)

    if df.empty:
        st.info("No expenses found in this date range.")
        return

    mask = pd.Series(True, index=df.index)

    if search_text.strip():
        mask &= df["description"].fillna("").str.contains(search_text.strip(), case=False, na=False)
    if selected_categories:
        mask &= df["category"].isin(selected_categories)
    if selected_users:
        mask &= df["added_by"].isin(selected_users)
    if min_amount > 0:
        mask &= df["amount"] >= min_amount
    if max_amount > 0:
        mask &= df["amount"] <= max_amount

    filtered = df[mask]

    if filtered.empty:
        st.info("No expenses match your filters.")
        return

    # Summary metrics
    total = filtered["amount"].sum()
    avg = filtered["amount"].mean()
    count = len(filtered)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total", f"${total:,.2f}")
    m2.metric("Average", f"${avg:,.2f}")
    m3.metric("Count", f"{count}")

    # Results table
    display = filtered[["date", "amount", "category", "description", "added_by"]].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
    display["Amount"] = filtered["amount"].map("${:,.2f}".format)
    st.dataframe(display, use_container_width=True, hide_index=True)


def page_manage_expenses(username: str):
    st.header("Manage Expenses")

    # --- Edit form (shown when editing) ---
    editing_id = st.session_state.get("editing_expense_id")
    if editing_id is not None:
        expense = get_expense_by_id(editing_id)
        if expense is None:
            st.error("Expense not found.")
            st.session_state.pop("editing_expense_id", None)
            st.rerun()
            return

        st.subheader(f"Edit Expense #{editing_id}")
        with st.form("edit_expense_form"):
            col1, col2 = st.columns(2)
            with col1:
                e_date = st.date_input("Date", value=datetime.strptime(expense["date"], "%Y-%m-%d").date())
            with col2:
                e_amount = st.number_input(
                    "Amount ($)", min_value=0.01, max_value=MAX_AMOUNT,
                    step=0.01, format="%.2f", value=float(expense["amount"]),
                )
            cat_idx = CATEGORIES.index(expense["category"]) if expense["category"] in CATEGORIES else 0
            e_category = st.selectbox("Category", CATEGORIES, index=cat_idx)
            e_description = st.text_input("Description", value=expense["description"] or "",
                                          max_chars=MAX_DESCRIPTION_LENGTH)

            col_save, col_cancel = st.columns(2)
            with col_save:
                save = st.form_submit_button("Save Changes", use_container_width=True)
            with col_cancel:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

            if save:
                valid, msg = validate_expense(
                    e_amount, e_category, e_description.strip(),
                    confirm_duplicate=True,
                )
                if not valid:
                    st.error(msg)
                else:
                    update_expense(editing_id, e_date, e_amount, e_category, e_description.strip())
                    st.session_state.pop("editing_expense_id", None)
                    st.success("Expense updated!")
                    st.rerun()
            if cancel:
                st.session_state.pop("editing_expense_id", None)
                st.rerun()
        return  # Don't show the rest while editing

    # --- Expense list with edit/delete ---
    st.caption("Select a date range to find expenses to edit or delete.")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=date.today().replace(day=1), key="manage_start")
    with col2:
        end = st.date_input("To", value=date.today(), key="manage_end")

    rows = get_expenses_between(start, end)
    if not rows:
        st.info("No expenses in this range.")
        return

    for row in rows:
        col_info, col_edit, col_del = st.columns([5, 1, 1])
        with col_info:
            st.markdown(
                f"**{row['date']}** | ${row['amount']:,.2f} | "
                f"{row['category']} | {row['description'] or '—'} "
                f"*(by {row['added_by']})*"
            )
        with col_edit:
            if st.button("Edit", key=f"edit_exp_{row['id']}"):
                st.session_state["editing_expense_id"] = row["id"]
                st.rerun()
        with col_del:
            if st.button("Delete", key=f"del_exp_{row['id']}"):
                delete_expense(row["id"])
                st.success("Expense deleted!")
                st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    inject_pwa()
    inject_mobile_css()
    authenticator, name, auth_status, username = authenticate()

    if auth_status is False:
        st.error("Username or password is incorrect.")
        return
    if auth_status is None:
        st.warning("Please enter your credentials.")
        return

    # Process recurring expenses once per session
    if "recurring_processed" not in st.session_state:
        process_recurring_expenses()
        st.session_state["recurring_processed"] = True

    # Logged in
    st.sidebar.title(f"Hi, {name}!")
    authenticator.logout("Logout", "sidebar")

    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Add Expense", "Monthly View", "Analysis",
         "Search", "Budgets", "Recurring", "Manage Expenses"],
    )

    pages = {
        "Dashboard": page_dashboard,
        "Add Expense": page_add_expense,
        "Monthly View": page_monthly_view,
        "Analysis": page_analysis,
        "Search": page_search,
        "Budgets": page_budgets,
        "Recurring": page_recurring,
        "Manage Expenses": page_manage_expenses,
    }
    pages[page](username)


if __name__ == "__main__":
    main()
