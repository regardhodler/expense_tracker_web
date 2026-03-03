"""Expense Tracker — Streamlit app for couples to track shared expenses."""

import calendar
import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from database import (
    init_db, add_expense, delete_expense, get_expenses_between, get_recent_expenses,
    get_budgets, set_budget, get_monthly_category_totals,
    add_recurring_expense, get_recurring_expenses, deactivate_recurring_expense,
    update_recurring_expense, process_recurring_expenses,
)
from analysis import (
    CATEGORIES, PERIOD_OPTIONS, rows_to_dataframe,
    get_period_dates, category_summary, daily_totals_for_month,
)
from visualization import pie_chart, bar_chart, monthly_trend_chart
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

    col1, col2 = st.columns(2)
    col1.metric("This Month", f"${month_total:,.2f}")
    col2.metric("Year to Date", f"${ytd_total:,.2f}")

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

    # Calendar-like grid
    st.subheader(f"{calendar.month_name[month]} {year}")
    daily = daily_totals_for_month(df, year, month)

    # Build calendar grid
    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = cal.monthdayscalendar(year, month)

    # Header row
    header_cols = st.columns(7)
    for i, day_name in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
        header_cols[i].markdown(f"**{day_name}**")

    for week in weeks:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            else:
                spent = daily.get(day, 0)
                if spent > 0:
                    cols[i].markdown(f"**{day}**  \n🔴 ${spent:,.0f}")
                else:
                    cols[i].markdown(f"{day}")

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
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pie Chart")
        st.plotly_chart(pie_chart(summary), use_container_width=True)
    with col2:
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


def page_delete_expense(username: str):
    st.header("Delete Expense")
    st.caption("Select a date range to find expenses to delete.")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=date.today().replace(day=1), key="del_start")
    with col2:
        end = st.date_input("To", value=date.today(), key="del_end")

    rows = get_expenses_between(start, end)
    if not rows:
        st.info("No expenses in this range.")
        return

    df = pd.DataFrame(rows)
    df_display = df[["id", "date", "amount", "category", "description", "added_by"]].copy()
    df_display.columns = ["ID", "Date", "Amount", "Category", "Description", "Added By"]

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    expense_id = st.number_input(
        "Enter expense ID to delete",
        min_value=0, step=1, value=0,
        help="Find the ID from the table above",
    )

    if expense_id > 0:
        target = next((r for r in rows if r["id"] == expense_id), None)
        if target:
            st.warning(
                f"Delete: **{target['date']}** | ${target['amount']:,.2f} | "
                f"{target['category']} | {target['description']} (by {target['added_by']})"
            )
            if st.button("Confirm Delete", type="primary"):
                delete_expense(expense_id)
                st.success("Expense deleted!")
                st.rerun()
        else:
            st.error("ID not found in current results.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    inject_pwa()
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
         "Budgets", "Recurring", "Delete Expense"],
    )

    pages = {
        "Dashboard": page_dashboard,
        "Add Expense": page_add_expense,
        "Monthly View": page_monthly_view,
        "Analysis": page_analysis,
        "Budgets": page_budgets,
        "Recurring": page_recurring,
        "Delete Expense": page_delete_expense,
    }
    pages[page](username)


if __name__ == "__main__":
    main()
