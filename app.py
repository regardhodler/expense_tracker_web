"""Expense Tracker — Streamlit app for couples to track shared expenses."""

import calendar
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from database import init_db, add_expense, delete_expense, get_expenses_between, get_recent_expenses
from analysis import (
    CATEGORIES, PERIOD_OPTIONS, rows_to_dataframe,
    get_period_dates, category_summary, daily_totals_for_month,
)
from visualization import pie_chart, bar_chart, monthly_trend_chart

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
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01, format="%.2f")

        category = st.selectbox("Category", CATEGORIES)

        if category == "Others":
            description = st.text_input("Description (required for Others)", "")
        else:
            description = st.text_input("Description (optional)", "")

        submitted = st.form_submit_button("Add Expense", use_container_width=True)

        if submitted:
            if amount <= 0:
                st.error("Amount must be positive.")
            elif category == "Others" and not description.strip():
                st.error("Description is required for 'Others' category.")
            else:
                add_expense(exp_date, amount, category, description.strip(), username)
                st.success(f"Added ${amount:,.2f} for {category} on {exp_date}!")


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

    # Logged in
    st.sidebar.title(f"Hi, {name}!")
    authenticator.logout("Logout", "sidebar")

    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Add Expense", "Monthly View", "Analysis", "Delete Expense"],
    )

    pages = {
        "Dashboard": page_dashboard,
        "Add Expense": page_add_expense,
        "Monthly View": page_monthly_view,
        "Analysis": page_analysis,
        "Delete Expense": page_delete_expense,
    }
    pages[page](username)


if __name__ == "__main__":
    main()
