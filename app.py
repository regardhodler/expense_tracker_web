"""Expense Tracker — Streamlit app for couples to track shared expenses."""

import calendar
import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

from database import (
    init_db, add_expense, delete_expense, get_expenses_between, get_recent_expenses,
    get_expense_by_id, update_expense, get_tax_writeoffs,
    get_budgets, set_budget, get_monthly_category_totals,
    add_recurring_expense, get_recurring_expenses, deactivate_recurring_expense,
    update_recurring_expense, process_recurring_expenses,
    get_savings_goals, add_savings_goal, update_savings_goal_progress,
    complete_savings_goal, delete_savings_goal,
    add_date_night, get_date_nights, get_date_night_dates, delete_date_night,
)
from analysis import (
    CATEGORIES, PERIOD_OPTIONS, rows_to_dataframe,
    get_period_dates, category_summary, daily_totals_for_month,
    expenses_for_day, spending_projections, month_comparison,
    love_points, LOVE_TIERS, LOVE_MESSAGES, canadian_comparison, DISPLAY_NAMES,
    get_streaks, get_monthly_challenges, get_achievements,
    get_love_history, get_who_spends_more,
)
from visualization import (
    pie_chart, bar_chart, monthly_trend_chart, comparison_bar_chart,
    canadian_comparison_chart, spending_heatmap, love_history_chart,
    who_spends_more_chart, savings_goal_chart,
)
from validation import validate_expense, MAX_AMOUNT, MAX_DESCRIPTION_LENGTH

# ---------------------------------------------------------------------------
# Cached dashboard queries (short TTL to avoid stale data on reruns)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def _cached_expenses_between(start_iso: str, end_iso: str) -> list[dict]:
    return get_expenses_between(date.fromisoformat(start_iso), date.fromisoformat(end_iso))

@st.cache_data(ttl=60)
def _cached_recent_expenses(limit: int) -> list[dict]:
    return get_recent_expenses(limit)

@st.cache_data(ttl=60)
def _cached_budgets() -> list[dict]:
    return get_budgets()

@st.cache_data(ttl=60)
def _cached_monthly_category_totals(year: int, month: int) -> dict:
    return get_monthly_category_totals(year, month)


@st.cache_data(ttl=300)
def _cached_all_expenses() -> list[dict]:
    """Fetch all expenses since 2020-01-01 for achievements/streaks/history."""
    from datetime import date as _date
    return get_expenses_between(_date(2020, 1, 1), _date.today())

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


def inject_romantic_css():
    """Subtle pink accent styling for the love dashboard."""
    st.markdown("""
        <style>
        [data-testid="stMetric"] {
            border-left: 4px solid #ff6b9d;
            padding-left: 12px;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
            color: #ff6b9d;
        }
        </style>
    """, unsafe_allow_html=True)


def inject_dark_mode_css(dark_mode: bool):
    """Inject light mode CSS overrides when dark_mode is False."""
    if not dark_mode:
        st.markdown("""
            <style>
            .stApp { background-color: #f8f9fa !important; color: #212529 !important; }
            [data-testid="stSidebar"] { background-color: #e9ecef !important; }
            [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: #212529 !important; }
            [data-testid="stMetricValue"] { color: #212529 !important; }
            </style>
        """, unsafe_allow_html=True)


def _monthsary_banner():
    """Show a celebratory banner on/around the 16th of each month."""
    today = date.today()

    MONTHSARY_MESSAGES = [
        "Happy Monthsary! Another beautiful chapter in the Jude & Wincyl story 💕",
        "Happy Monthsary! Still falling for each other, one expense at a time 💕",
        "Happy Monthsary! Love isn't counted in dollars — but we track those too 💕",
        "Happy Monthsary! Another month of being each other's favorite person 💕",
        "Happy Monthsary! The best things in life aren't expenses... but we log them anyway 💕",
    ]
    LOVE_FACTS = [
        "Fun fact: Couples who budget together stay together!",
        "Did you know? Shared financial goals strengthen relationships.",
        "Love tip: It's not about who spends more — it's about spending time together.",
        "Fact: The average couple talks about money 3x a week. You two track it!",
        "Remember: The best investment is in each other.",
    ]

    if today.day == 16:
        st.balloons()
        msg_idx = (today.year * 12 + today.month) % len(MONTHSARY_MESSAGES)
        fact_idx = (today.year * 12 + today.month + 3) % len(LOVE_FACTS)
        st.markdown(
            f'<div style="text-align:center;padding:20px;background:linear-gradient(135deg,#ff6b9d,#c44dff);'
            f'border-radius:12px;margin:10px 0">'
            f'<h2 style="color:white;margin:0">💕 {MONTHSARY_MESSAGES[msg_idx]}</h2>'
            f'<p style="color:#ffe0f0;margin:8px 0 0;font-style:italic">{LOVE_FACTS[fact_idx]}</p>'
            f'</div>', unsafe_allow_html=True)
    elif today.day in (15, 17):
        st.info("💕 Monthsary is on the 16th! Love you always.")


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

st.set_page_config(page_title="Jude & Wincyl's Expense Tracker", page_icon="💕", layout="wide")


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
                    "name": "Jude",
                    "password": hashed[0],
                },
                "wife": {
                    "email": "wife@home.local",
                    "name": "Wincyl",
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
    st.header("💕 Jude & Wincyl's Love Dashboard")
    _monthsary_banner()
    today = date.today()

    # Quick stats
    month_start = today.replace(day=1)
    year_start = date(today.year, 1, 1)
    month_rows = _cached_expenses_between(month_start.isoformat(), today.isoformat())
    ytd_rows = _cached_expenses_between(year_start.isoformat(), today.isoformat())
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
    prev_month_rows = _cached_expenses_between(prev_month_start.isoformat(), prev_month_end.isoformat())
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

    # Love Points
    st.subheader("💕 Romance Status")
    lp = love_points(rows_to_dataframe(month_rows))

    # 1. Love Message Banner
    next_month_name = calendar.month_name[today.month % 12 + 1] if today.month < 12 else "January"
    st.markdown(
        f'<div style="text-align:center;padding:24px 20px;'
        f'background:linear-gradient(135deg,#ff6b9d,#c44dff);'
        f'border-radius:14px;margin:10px 0">'
        f'<h2 style="color:white;margin:0;font-size:1.8em">{lp["emoji"]} {lp["message"]}</h2>'
        f'<p style="color:#ffe0f0;margin:5px 0 0;font-size:0.9em">'
        f'Combined Love Points: {lp["combined_points"]:.1f} · Resets {next_month_name} 1st</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 2. Shared Love Meter
    _MAX_METER = 25  # bar fills completely at 25 pts
    if lp["combined_points"] >= _MAX_METER:
        progress_pct = 100
        _egg_msgs = LOVE_MESSAGES["easter_egg"]
        _egg_msg = _egg_msgs[int(lp["combined_points"]) % len(_egg_msgs)]
        right_label = f'🌟 {_egg_msg}'
    elif lp["next_tier_threshold"] is not None:
        progress_pct = min(lp["combined_points"] / _MAX_METER, 1.0) * 100
        next_tier = LOVE_TIERS[LOVE_TIERS.index(
            next(t for t in LOVE_TIERS if t["name"] == lp["tier"])
        ) + 1]
        right_label = (f'{lp["combined_points"]:.1f} / {lp["next_tier_threshold"]} pts to '
                       f'{next_tier["emoji"]} {next_tier["label"]}')
    else:
        progress_pct = 100
        right_label = "MAX LOVE REACHED!"

    st.markdown(
        f'<div style="margin:16px 0">'
        f'<div style="display:flex;justify-content:space-between;color:#ccc;font-size:0.8em;margin-bottom:6px">'
        f'<span>💕 Love Meter — <strong style="color:#ff6b9d">{lp["label"]}</strong></span>'
        f'<span>{right_label}</span></div>'
        f'<div style="background:#2a2a4a;border-radius:10px;height:24px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#ff6b9d,#c44dff);width:{progress_pct:.1f}%;'
        f'height:100%;border-radius:10px"></div></div>'
        f'<div style="display:flex;justify-content:space-between;color:#666;font-size:0.65em;margin-top:4px">'
        f'<span>❄️0</span><span>🥰3</span><span>😍6</span><span>💕9</span><span>🔥12</span>'
        f'<span>💘15</span><span>🫂18</span><span>👑21</span><span>💪25</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 3. Individual Contribution Bars
    from analysis import DISPLAY_NAMES
    h_pts = lp["points"]["husband"]
    w_pts = lp["points"]["wife"]
    total_pts = lp["combined_points"]
    h_pct = (h_pts / total_pts * 100) if total_pts > 0 else 0
    w_pct = (w_pts / total_pts * 100) if total_pts > 0 else 0

    st.markdown(
        f'<div style="display:flex;gap:16px;margin:12px 0">'
        f'<div style="flex:1">'
        f'<div style="color:#ccc;font-size:0.8em;margin-bottom:4px">'
        f'💙 {DISPLAY_NAMES["husband"]} — <strong>{h_pts:.1f} pts</strong></div>'
        f'<div style="background:#2a2a4a;border-radius:8px;height:18px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#4a8cff,#6ba3ff);width:{h_pct:.1f}%;'
        f'height:100%;border-radius:8px"></div></div></div>'
        f'<div style="flex:1">'
        f'<div style="color:#ccc;font-size:0.8em;margin-bottom:4px">'
        f'💗 {DISPLAY_NAMES["wife"]} — <strong>{w_pts:.1f} pts</strong></div>'
        f'<div style="background:#2a2a4a;border-radius:8px;height:18px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#ff6b9d,#ff8fb3);width:{w_pct:.1f}%;'
        f'height:100%;border-radius:8px"></div></div></div></div>',
        unsafe_allow_html=True,
    )

    # --- Streak badge + Forecast ---
    all_rows_for_streaks = _cached_all_expenses()
    streaks = get_streaks(all_rows_for_streaks)
    cur_streak = streaks["current_streak"]
    if cur_streak > 0:
        streak_color = "#ff6600"
        streak_html = f'🔥 <strong style="color:{streak_color}">{cur_streak} day streak!</strong> Keep it up!'
    else:
        streak_color = "#666"
        streak_html = '😴 No active streak — log today to start one!'

    fc_html = ""
    if month_rows and prev_month_total > 0:
        proj = spending_projections(month_rows, month_start, today)
        pct_diff = (proj["projected_total"] - prev_month_total) / prev_month_total * 100
        direction = "more" if pct_diff >= 0 else "less"
        arrow = "📈" if pct_diff >= 0 else "📉"
        fc_html = (f'{arrow} On track for <strong>${proj["projected_total"]:,.0f}</strong> this month '
                   f'vs <strong>${prev_month_total:,.0f}</strong> last month — '
                   f'<strong>{abs(pct_diff):.0f}% {direction}</strong>')

    st.markdown(
        f'<div style="display:flex;gap:12px;margin:12px 0;flex-wrap:wrap">'
        f'<div style="background:#1a1a2e;border-radius:12px;padding:12px 18px;flex:1;min-width:180px;border-left:4px solid {streak_color}">'
        f'<span style="color:#ccc;font-size:0.9em">{streak_html}</span></div>'
        + (f'<div style="background:#1a1a2e;border-radius:12px;padding:12px 18px;flex:2;min-width:260px;border-left:4px solid #c44dff">'
           f'<span style="color:#ccc;font-size:0.9em">{fc_html}</span></div>' if fc_html else "")
        + f'</div>',
        unsafe_allow_html=True,
    )

    # --- Monthly Challenges ---
    budgets_for_challenges = _cached_budgets()
    challenges = get_monthly_challenges(month_rows, prev_month_total, budgets_for_challenges)
    with st.expander("🎯 This Month's Challenges"):
        ch_cols = st.columns(min(len(challenges), 3))
        for i, ch in enumerate(challenges):
            with ch_cols[i % len(ch_cols)]:
                status_icon = "✅" if ch["completed"] else ("❌" if ch["detail"].startswith("❌") else "⏳")
                pct = ch["progress_pct"]
                bar_color = "#2ecc71" if ch["completed"] else "linear-gradient(90deg,#ff6b9d,#c44dff)"
                st.markdown(
                    f'<div style="background:#1a1a2e;border-radius:10px;padding:12px;margin:4px 0;min-height:110px">'
                    f'<div style="font-size:1.4em">{ch["emoji"]} {status_icon}</div>'
                    f'<div style="font-weight:bold;color:#e0e0e0;margin:4px 0">{ch["title"]}</div>'
                    f'<div style="color:#999;font-size:0.75em;margin-bottom:6px">{ch["description"]}</div>'
                    f'<div style="background:#2a2a4a;border-radius:6px;height:8px;overflow:hidden;margin-bottom:4px">'
                    f'<div style="background:{"#2ecc71" if ch["completed"] else "linear-gradient(90deg,#ff6b9d,#c44dff)"};'
                    f'width:{pct:.1f}%;height:100%;border-radius:6px"></div></div>'
                    f'<div style="color:#777;font-size:0.7em">{ch["detail"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # --- Achievements ---
    achievements = get_achievements(all_rows_for_streaks)
    with st.expander("🏆 Achievements"):
        unlocked = [a for a in achievements if a["unlocked"]]
        locked = [a for a in achievements if not a["unlocked"]]
        if unlocked:
            st.markdown(f"**{len(unlocked)} / {len(achievements)} unlocked**")
        ach_cols = st.columns(min(len(achievements), 4))
        for i, ach in enumerate(achievements):
            with ach_cols[i % len(ach_cols)]:
                opacity = "1" if ach["unlocked"] else "0.35"
                border = "#c44dff" if ach["unlocked"] else "#333"
                date_str = f"<br><span style='color:#888;font-size:0.65em'>Unlocked: {ach['unlocked_date']}</span>" if ach["unlocked_date"] else ""
                st.markdown(
                    f'<div style="background:#1a1a2e;border-radius:10px;padding:10px;margin:4px 0;'
                    f'border:1px solid {border};opacity:{opacity};text-align:center">'
                    f'<div style="font-size:1.8em">{ach["emoji"]}</div>'
                    f'<div style="font-weight:bold;color:#e0e0e0;font-size:0.8em">{ach["name"]}</div>'
                    f'<div style="color:#999;font-size:0.7em">{ach["description"]}{date_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # --- Love History ---
    love_hist = get_love_history(all_rows_for_streaks)
    if love_hist:
        with st.expander("📈 Love History"):
            st.plotly_chart(love_history_chart(love_hist), use_container_width=True)

    # --- Our Story This Year ---
    year_start_dn = date(today.year, 1, 1)
    ytd_dates = get_date_nights(year_start_dn, today)
    if ytd_dates:
        with st.expander(f"💌 Our Story This Year — {len(ytd_dates)} date{'s' if len(ytd_dates) != 1 else ''}", expanded=True):
            # Summary stats row
            last_dn = ytd_dates[0]  # newest first
            last_dn_date = date.fromisoformat(last_dn["night_date"])
            days_since = (today - last_dn_date).days

            # Expenses on date nights — only the tagged expense amount
            dn_expense_total = sum(dn.get("expense_amount") or 0.0 for dn in ytd_dates)

            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("💕 Dates this year", len(ytd_dates))
            sc2.metric("💸 Invested in us", f"${dn_expense_total:,.2f}")
            if days_since == 0:
                sc3.metric("🌹 Last date", "Today!")
            elif days_since == 1:
                sc3.metric("🌹 Last date", "Yesterday")
            else:
                sc3.metric("🌹 Last date", f"{days_since}d ago")

            # Timeline
            st.markdown("---")
            VIBE_EMOJI = {
                "Romantic dinner": "🍷",
                "Chill & cozy": "🛋️",
                "Fun & adventurous": "🎉",
                "Spontaneous": "⚡",
                "Special occasion": "🎂",
                "Just us, no plans": "🌙",
                "First of its kind": "🌟",
            }
            WHERE_EMOJI = {
                "Restaurant": "🍽️",
                "Movie / Theatre": "🎬",
                "Home date night": "🏠",
                "Cafe / Coffee shop": "☕",
                "Park / Walk": "🌿",
                "Shopping together": "🛍️",
                "Concert / Event": "🎵",
                "Other": "📍",
            }
            for dn in ytd_dates:
                dn_d = date.fromisoformat(dn["night_date"])
                w_emoji = WHERE_EMOJI.get(dn["where_text"], "📍")
                v_emoji = VIBE_EMOJI.get(dn["how_text"], "💕")
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:14px;'
                    f'padding:10px 14px;margin:4px 0;border-radius:10px;'
                    f'background:linear-gradient(90deg,#2a0d1f,#1a0a12);border-left:3px solid #ff6b9d">'
                    f'<div style="min-width:70px;color:#ff9fd2;font-size:0.85em;font-weight:bold">'
                    f'{dn_d.strftime("%b %d")}</div>'
                    f'<div style="font-size:1.4em">{w_emoji}</div>'
                    f'<div style="flex:1">'
                    f'<span style="color:#ffe0f0;font-size:0.95em">{dn["where_text"]}</span>'
                    f'</div>'
                    f'<div style="font-size:1.2em">{v_emoji}</div>'
                    f'<div style="color:#ccc;font-size:0.82em;font-style:italic">{dn["how_text"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        with st.expander("💌 Our Story This Year"):
            st.markdown(
                '<div style="text-align:center;padding:28px;color:#888;font-size:0.95em">'
                '💕 No date nights recorded yet this year.<br>'
                '<span style="font-size:0.85em">Next time you add an expense, tap <strong>💕 Mark it!</strong> to log your date.</span>'
                '</div>',
                unsafe_allow_html=True,
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

                # Total spending summary row
                _total_delta = cur_t - prev_t
                _total_pct = ((_total_delta / prev_t) * 100) if prev_t else 0
                _delta_color = "#ef4444" if _total_delta > 0 else "#4ade80"
                _delta_arrow = "▲" if _total_delta > 0 else "▼"
                _cur_label_s = today.strftime("%b %Y")
                _prev_label_s = (today.replace(day=1) - pd.Timedelta(days=1)).strftime("%b %Y")
                st.markdown(
                    f"""<div style="background:#1a1a2e;border-radius:10px;padding:14px 18px;margin:6px 0;display:flex;gap:32px;align-items:center">
                    <div><span style="color:#aaa;font-size:0.8rem">TOTAL {_cur_label_s.upper()}</span><br>
                    <span style="font-size:1.2rem;font-weight:700;color:#fff">${cur_t:,.2f}</span></div>
                    <div><span style="color:#aaa;font-size:0.8rem">TOTAL {_prev_label_s.upper()}</span><br>
                    <span style="font-size:1.2rem;font-weight:700;color:#fff">${prev_t:,.2f}</span></div>
                    <div><span style="color:#aaa;font-size:0.8rem">CHANGE</span><br>
                    <span style="font-size:1.2rem;font-weight:700;color:{_delta_color}">{_delta_arrow} ${abs(_total_delta):,.2f} ({_total_pct:+.1f}%)</span></div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.caption("💡 Click a category bar to see its transactions below")
                _dash_bar_sel = st.plotly_chart(
                    comparison_bar_chart(comp_df),
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="points",
                    key="dashboard_comparison_chart",
                )
                _dash_selected_cat = None
                if _dash_bar_sel and _dash_bar_sel.selection and _dash_bar_sel.selection.get("points"):
                    _dash_selected_cat = _dash_bar_sel.selection["points"][0].get("x")
                if _dash_selected_cat:
                    _cur_label = today.strftime("%B %Y")
                    _prev_label = (today.replace(day=1) - pd.Timedelta(days=1)).strftime("%B %Y")
                    st.markdown(f"### 📋 {_dash_selected_cat} transactions")
                    _tab_cur, _tab_prev = st.tabs([f"Current ({_cur_label})", f"Previous ({_prev_label})"])
                    with _tab_cur:
                        _cur_cat = [r for r in month_rows if r["category"] == _dash_selected_cat]
                        if _cur_cat:
                            _cur_cat_df = pd.DataFrame(_cur_cat)[["date", "amount", "description", "added_by"]]
                            _cur_cat_df.columns = ["Date", "Amount", "Description", "Added By"]
                            _cur_cat_df = _cur_cat_df.sort_values("Date", ascending=False)
                            _cur_cat_df["Amount"] = _cur_cat_df["Amount"].map("${:,.2f}".format)
                            st.dataframe(_cur_cat_df, use_container_width=True, hide_index=True)
                            st.caption(f"Total: **${sum(r['amount'] for r in _cur_cat):,.2f}** across {len(_cur_cat)} transaction(s)")
                        else:
                            st.info(f"No {_dash_selected_cat} transactions this month.")
                    with _tab_prev:
                        _prev_cat = [r for r in prev_month_rows if r["category"] == _dash_selected_cat]
                        if _prev_cat:
                            _prev_cat_df = pd.DataFrame(_prev_cat)[["date", "amount", "description", "added_by"]]
                            _prev_cat_df.columns = ["Date", "Amount", "Description", "Added By"]
                            _prev_cat_df = _prev_cat_df.sort_values("Date", ascending=False)
                            _prev_cat_df["Amount"] = _prev_cat_df["Amount"].map("${:,.2f}".format)
                            st.dataframe(_prev_cat_df, use_container_width=True, hide_index=True)
                            st.caption(f"Total: **${sum(r['amount'] for r in _prev_cat):,.2f}** across {len(_prev_cat)} transaction(s)")
                        else:
                            st.info(f"No {_dash_selected_cat} transactions last month.")
            else:
                st.info("No data to compare.")

    # Spending heatmap
    st.subheader("📅 Spending Heatmap")
    month_df = rows_to_dataframe(month_rows)
    st.plotly_chart(spending_heatmap(month_df, today.year, today.month), use_container_width=True)

    # Who spends more?
    if month_rows:
        st.subheader("💰 Who Spends More This Month?")
        wsm_df = get_who_spends_more(rows_to_dataframe(month_rows))
        if not wsm_df.empty:
            st.plotly_chart(who_spends_more_chart(wsm_df), use_container_width=True)
            st.dataframe(wsm_df, use_container_width=True, hide_index=True)

    # Over-budget warnings
    budgets = _cached_budgets()
    if budgets:
        category_totals = _cached_monthly_category_totals(today.year, today.month)
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
    recent = _cached_recent_expenses(10)
    if recent:
        df = pd.DataFrame(recent)
        df_display = df[["date", "amount", "category", "description", "added_by"]].copy()
        df_display.columns = ["Date", "Amount", "Category", "Description", "Added By"]
        df_display["Amount"] = df_display["Amount"].map("${:,.2f}".format)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("No expenses yet. Add your first one!")



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

        added_for = st.selectbox("Who is this for?", ["Jude", "Wincyl"], key="add_expense_for")
        is_writeoff = st.checkbox("🧾 Tax Write-Off", value=False)

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
                from analysis import DISPLAY_NAMES
                added_by = next((k for k, v in DISPLAY_NAMES.items() if v == added_for), username)
                add_expense(exp_date, amount, category, description.strip(), added_by, is_writeoff)
                st.success(f"Added ${amount:,.2f} for {category} on {exp_date}!")
                st.session_state.pop("_confirm_duplicate", None)
                st.session_state["_date_night_pending"] = (exp_date, amount)

    # --- Date Night Tagging (outside form so it survives rerun) ---
    if "_date_night_pending" in st.session_state:
        pending_date, pending_amount = st.session_state["_date_night_pending"]
        st.markdown(
            '<div style="background:linear-gradient(135deg,#3d1a4f,#6b1a3a);'
            'border-radius:14px;padding:18px 22px;margin:12px 0;border:1px solid #ff6b9d">'
            '<span style="font-size:1.3em">💕</span> '
            '<strong style="color:#ff9fd2;font-size:1.05em">Was this a date night with Jude & Wincyl?</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        dn_col1, dn_col2, dn_col3 = st.columns([2, 2, 1])
        with dn_col1:
            dn_where = st.selectbox(
                "📍 Where?",
                ["Restaurant", "Movie / Theatre", "Home date night", "Cafe / Coffee shop",
                 "Park / Walk", "Shopping together", "Concert / Event", "Other"],
                key="_dn_where",
            )
        with dn_col2:
            dn_how = st.selectbox(
                "✨ Vibe?",
                ["Romantic dinner", "Chill & cozy", "Fun & adventurous", "Spontaneous",
                 "Special occasion", "Just us, no plans", "First of its kind"],
                key="_dn_how",
            )
        with dn_col3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("💕 Mark it!", use_container_width=True, key="_dn_confirm"):
                add_date_night(pending_date, dn_where, dn_how, pending_amount)
                st.session_state.pop("_date_night_pending", None)
                st.balloons()
                st.success(f"💕 {pending_date.strftime('%B %d')} is now a date night! 🌹")
                st.rerun()
        if st.button("Skip", key="_dn_skip", type="secondary"):
            st.session_state.pop("_date_night_pending", None)
            st.rerun()


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
        "Utilities": "#FF5722",
        "Others": "#607D8B",
    }

    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = cal.monthdayscalendar(year, month)

    date_night_days = get_date_night_dates(year, month)

    TH_STYLE = "background:#1a1a2e;color:#ccc;padding:6px;text-align:center;border:1px solid #333;font-size:0.85em"
    TD_STYLE = "border:1px solid #333;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#0e1117"
    TD_TODAY = "border:2px solid #4a8cff;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#1a2744"
    TD_DATE_NIGHT = "border:2px solid #ff6b9d;vertical-align:top;padding:4px 6px;height:80px;font-size:0.8em;background:#2a0d1f"
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
                is_date_night = day in date_night_days
                if is_today:
                    style = TD_TODAY
                elif is_date_night:
                    style = TD_DATE_NIGHT
                else:
                    style = TD_STYLE
                day_expenses = expenses_for_day(df, current_date)

                html += f'<td style="{style}">'
                day_label = f'{day} 💕' if is_date_night else str(day)
                html += f'<div style="font-weight:bold;color:#e0e0e0;margin-bottom:3px;font-size:0.95em">{day_label}</div>'

                if not day_expenses.empty:
                    for _, exp in day_expenses.iterrows():
                        cat = exp["category"]
                        color = CATEGORY_COLORS.get(cat, "#999")
                        amt = exp["amount"]
                        desc = exp.get("description", "") or ""
                        is_recurring = desc.startswith("[Recurring]")
                        icon = "&#x21BB; " if is_recurring else ""
                        tooltip = (desc.replace("&", "&amp;").replace("<", "&lt;")
                                      .replace(">", "&gt;").replace('"', "&quot;"))
                        html += (
                            f'<div title="{tooltip}" style="color:{color};white-space:nowrap;overflow:hidden;'
                            f'text-overflow:ellipsis;font-size:0.75em;line-height:1.4;cursor:default">'
                            f'{icon}${amt:,.0f} {cat}</div>'
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
    if date_night_days:
        st.markdown(
            '<p style="color:#ff9fd2;font-size:0.8em;margin-top:6px">💕 Pink glow = date night</p>',
            unsafe_allow_html=True,
        )
    st.markdown(html, unsafe_allow_html=True)

    # Day details selector
    st.subheader("📋 Day Details")
    default_day = today.day if year == today.year and month == today.month else 1
    selected_day = st.number_input("Select day", min_value=1, max_value=last_day,
                                    value=default_day, key="day_detail_select")
    selected_date = date(year, month, selected_day)
    day_exps = expenses_for_day(df, selected_date)

    if day_exps.empty:
        st.info(f"No expenses on {selected_date.strftime('%B %d, %Y')}.")
    else:
        day_total = day_exps["amount"].sum()
        st.metric(f"Total for {selected_date.strftime('%B %d')}", f"${day_total:,.2f}")
        for _, exp in day_exps.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{exp['category']}**")
                    st.caption(exp.get("description", "") or "No description")
                    st.caption(f"Added by: {exp['added_by']}")
                with c2:
                    st.markdown(f"**${exp['amount']:,.2f}**")

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
    st.caption("💡 Click a category bar to see its transactions below")
    _bar_sel = st.plotly_chart(
        bar_chart(summary),
        use_container_width=True,
        on_select="rerun",
        selection_mode="points",
        key="analysis_bar_chart",
    )
    _selected_cat = None
    if _bar_sel and _bar_sel.selection and _bar_sel.selection.get("points"):
        _selected_cat = _bar_sel.selection["points"][0].get("x")
    if _selected_cat:
        st.markdown(f"### 📋 {_selected_cat} transactions ({start.strftime('%b %d')} – {end.strftime('%b %d, %Y')})")
        _cat_df = df[df["category"] == _selected_cat].copy()
        _cat_df = _cat_df.sort_values("date", ascending=False)
        _cat_display = _cat_df[["date", "amount", "description", "added_by"]].copy()
        _cat_display.columns = ["Date", "Amount", "Description", "Added By"]
        _cat_display["Amount"] = _cat_display["Amount"].map("${:,.2f}".format)
        st.dataframe(_cat_display, use_container_width=True, hide_index=True)
        st.caption(f"Total: **${_cat_df['amount'].sum():,.2f}** across {len(_cat_df)} transaction(s)")

    # Monthly trend (if period spans multiple months)
    if (end - start).days > 31:
        st.subheader("Monthly Spending Trend")
        trend = monthly_trend_chart(df)
        if trend:
            st.plotly_chart(trend, use_container_width=True)

    # Canadian Average comparison
    st.subheader("🇨🇦 Your Monthly Average vs Canadian Average")
    st.caption("Your monthly average spending per category vs Canadian 2-person household averages (2023)")
    cdn = canadian_comparison(df, start, end)
    st.plotly_chart(canadian_comparison_chart(cdn), use_container_width=True)
    st.dataframe(cdn, use_container_width=True, hide_index=True)

    # --- Contributions Section ---
    st.divider()
    st.subheader("💰 Contributions")
    contrib_options = ["Weekly", "Monthly", "6 Months", "1 Year", "YTD"]
    contrib_period = st.selectbox("Filter by", contrib_options, key="contrib_filter")

    today = date.today()
    if contrib_period == "Weekly":
        c_start = today - pd.Timedelta(days=today.weekday())  # Monday
        c_end = today
    elif contrib_period == "Monthly":
        c_start = today.replace(day=1)
        c_end = today
    elif contrib_period == "6 Months":
        c_start = (today - pd.DateOffset(months=6)).date()
        c_end = today
    elif contrib_period == "1 Year":
        c_start = (today - pd.DateOffset(years=1)).date()
        c_end = today
    else:  # YTD
        c_start = today.replace(month=1, day=1)
        c_end = today

    contrib_rows = get_expenses_between(c_start, c_end)
    contrib_df = rows_to_dataframe(contrib_rows)

    if contrib_df.empty:
        st.info(f"No expenses found for {contrib_period}.")
    else:
        from analysis import DISPLAY_NAMES
        by_person = contrib_df.groupby("added_by")["amount"].sum().reset_index()
        by_person.columns = ["Person", "Total"]
        grand_total = by_person["Total"].sum()
        by_person["% Share"] = (by_person["Total"] / grand_total * 100).round(1)

        c1, c2 = st.columns(2)
        for i, col in enumerate([c1, c2]):
            if i < len(by_person):
                row = by_person.iloc[i]
                display = DISPLAY_NAMES.get(row["Person"], row["Person"])
                col.metric(display, f"${row['Total']:,.2f}", f"{row['% Share']}% of total")

        st.caption(f"Period: {c_start} to {c_end}")


def page_budgets(username: str):
    st.header("Budget Tracking")

    # Set budgets
    st.subheader("Set Monthly Budgets")
    with st.form("budget_form"):
        category = st.selectbox("Category", CATEGORIES)
        limit = st.number_input("Monthly Limit ($)", min_value=0.01, max_value=MAX_AMOUNT, step=10.0, format="%.2f")
        notes = st.text_area("Comments (optional)", placeholder="e.g. Includes groceries and dining out", max_chars=300)
        if st.form_submit_button("Set Budget", use_container_width=True):
            set_budget(category, limit, username, notes)
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
        if b.get("notes"):
            st.caption(f"💬 {b['notes']}")


def page_recurring(username: str):
    st.header("Recurring Expense")

    # --- Edit form (shown when editing) ---
    editing_id = st.session_state.get("editing_recurring_id")
    if editing_id is not None:
        recurring_all = get_recurring_expenses(active_only=True)
        edit_rec = next((r for r in recurring_all if r["id"] == editing_id), None)
        if edit_rec:
            st.subheader(f"Edit: {edit_rec['name']}")
            freq_options = ["monthly", "weekly", "biweekly"]
            if "edit_freq" not in st.session_state:
                st.session_state["edit_freq"] = edit_rec["frequency"] if edit_rec["frequency"] in freq_options else "monthly"
            e_frequency = st.selectbox("Frequency", freq_options, key="edit_freq")
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
                from analysis import DISPLAY_NAMES
                person_options = ["Jude", "Wincyl"]
                current_person = DISPLAY_NAMES.get(edit_rec.get("added_by", ""), "Jude")
                e_added_for = st.selectbox("Who is this for?", person_options,
                                           index=person_options.index(current_person) if current_person in person_options else 0,
                                           key="edit_recurring_for")
                if e_frequency == "monthly":
                    e_day_of_month = st.number_input("Day of Month", min_value=1, max_value=31,
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
                        e_added_by = next((k for k, v in DISPLAY_NAMES.items() if v == e_added_for), edit_rec.get("added_by"))
                        update_recurring_expense(
                            editing_id, e_name.strip(), e_amount, e_category,
                            e_description.strip(), e_frequency, e_day_of_month, e_start_date, e_added_by,
                        )
                        st.session_state.pop("editing_recurring_id", None)
                        st.session_state.pop("edit_freq", None)
                        st.session_state.pop("recurring_processed", None)
                        st.success("Recurring expense updated!")
                        st.rerun()
                if cancel:
                    st.session_state.pop("editing_recurring_id", None)
                    st.session_state.pop("edit_freq", None)
                    st.rerun()
            return  # Don't show the rest while editing

    # --- Add recurring ---
    st.subheader("Add Recurring Expense")
    frequency = st.selectbox("Frequency", ["monthly", "weekly", "biweekly"], key="add_freq")
    with st.form("recurring_form", clear_on_submit=True):
        name = st.text_input("Name (e.g. Rent, Netflix)", max_chars=100)
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount ($)", min_value=0.01, max_value=MAX_AMOUNT, step=0.01, format="%.2f")
        with col2:
            category = st.selectbox("Category", CATEGORIES)
        description = st.text_input("Description (optional)", "", max_chars=MAX_DESCRIPTION_LENGTH)
        added_for = st.selectbox("Who is this for?", ["Jude", "Wincyl"], key="recurring_expense_for")

        if frequency == "monthly":
            day_of_month = st.number_input("Day of Month", min_value=1, max_value=31, value=min(date.today().day, 28))
            start_date = None
        else:
            start_date_input = st.date_input("Start Date", value=date.today())
            start_date = start_date_input.isoformat()
            day_of_month = 1

        if st.form_submit_button("Add Recurring Expense", use_container_width=True):
            if not name.strip():
                st.error("Name is required.")
            else:
                from analysis import DISPLAY_NAMES
                added_by = next((k for k, v in DISPLAY_NAMES.items() if v == added_for), username)
                add_recurring_expense(
                    name.strip(), amount, category, description.strip(),
                    frequency, day_of_month, added_by, start_date,
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
                st.session_state.pop("recurring_processed", None)
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
            e_writeoff = st.checkbox("🧾 Tax Write-Off", value=bool(expense.get("is_tax_writeoff", 0)))

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
                    update_expense(editing_id, e_date, e_amount, e_category, e_description.strip(), e_writeoff)
                    st.session_state.pop("editing_expense_id", None)
                    st.success("Expense updated!")
                    st.rerun()
            if cancel:
                st.session_state.pop("editing_expense_id", None)
                st.rerun()
        return  # Don't show the rest while editing

    # --- Expense list with edit/delete ---
    # --- Tabs: Expense List | Tax Report ---
    tab_list, tab_tax = st.tabs(["📋 Expense List", "🧾 Tax Report"])

    with tab_list:
        st.caption("Select a date range to find expenses to edit or delete.")

        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("From", value=date.today().replace(day=1), key="manage_start")
        with col2:
            end = st.date_input("To", value=date.today(), key="manage_end")

        rows = get_expenses_between(start, end)
        if not rows:
            st.info("No expenses in this range.")
        else:
            for row in rows:
                writeoff_badge = " 🧾" if row.get("is_tax_writeoff") else ""
                col_info, col_edit, col_del = st.columns([5, 1, 1])
                with col_info:
                    st.markdown(
                        f"**{row['date']}** | ${row['amount']:,.2f} | "
                        f"{row['category']} | {row['description'] or '—'} "
                        f"*(by {row['added_by']})*{writeoff_badge}"
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

    with tab_tax:
        st.subheader("🧾 Tax Write-Offs")
        st.caption("All expenses marked as tax write-offs.")

        col1, col2 = st.columns(2)
        with col1:
            tax_start = st.date_input("From", value=date(date.today().year, 1, 1), key="tax_start")
        with col2:
            tax_end = st.date_input("To", value=date.today(), key="tax_end")

        tax_cat_filter = st.multiselect("Filter by Category", CATEGORIES, default=[], key="tax_cat_filter")

        writeoffs = get_tax_writeoffs(tax_start, tax_end)
        if tax_cat_filter:
            writeoffs = [r for r in writeoffs if r["category"] in tax_cat_filter]

        if not writeoffs:
            st.info("No tax write-offs found for this period.")
        else:
            cat_totals: dict[str, float] = {}
            for r in writeoffs:
                cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["amount"]
            grand_total = sum(cat_totals.values())

            st.markdown(
                f"""<div style="background:#1a1a2e;border-radius:12px;padding:16px;margin:8px 0">
                <span style="font-size:1.1rem;font-weight:700;color:#4ade80">
                Total Write-Offs: ${grand_total:,.2f}
                </span> &nbsp;·&nbsp;
                <span style="color:#aaa">{len(writeoffs)} expense(s)</span>
                </div>""",
                unsafe_allow_html=True,
            )

            with st.expander("📊 By Category", expanded=True):
                for cat, total in sorted(cat_totals.items(), key=lambda x: -x[1]):
                    pct = (total / grand_total * 100) if grand_total else 0
                    st.markdown(
                        f"**{cat}** — ${total:,.2f} &nbsp;<span style='color:#aaa;font-size:0.85rem'>({pct:.0f}%)</span>",
                        unsafe_allow_html=True,
                    )

            st.divider()
            for row in writeoffs:
                added_name = DISPLAY_NAMES.get(row["added_by"], row["added_by"])
                st.markdown(
                    f"🧾 **{row['date']}** | ${row['amount']:,.2f} | "
                    f"{row['category']} | {row['description'] or '—'} *(by {added_name})*"
                )

            st.divider()
            df_export = pd.DataFrame(writeoffs)[["date", "amount", "category", "description", "added_by"]]
            df_export["added_by"] = df_export["added_by"].map(lambda x: DISPLAY_NAMES.get(x, x))
            df_export.columns = ["Date", "Amount", "Category", "Description", "Added By"]
            csv_bytes = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export as CSV",
                data=csv_bytes,
                file_name=f"tax_writeoffs_{tax_start}_{tax_end}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
def page_savings_goals(username: str):
    st.header("🎯 Savings Goals")

    EMOJI_OPTIONS = ["🎯", "🏠", "✈️", "🚗", "💍", "📱", "💻", "🎓", "🏖️", "🛍️", "💰", "🎁", "🏋️", "🌟", "❤️"]

    # Add new goal form
    with st.expander("➕ Add New Goal", expanded=False):
        with st.form("add_goal_form", clear_on_submit=True):
            g_name = st.text_input("Goal Name (e.g. Vacation Fund)", max_chars=80)
            col1, col2 = st.columns(2)
            with col1:
                g_target = st.number_input("Target Amount ($)", min_value=1.0, max_value=1_000_000.0, step=100.0, format="%.2f")
            with col2:
                g_emoji = st.selectbox("Emoji", EMOJI_OPTIONS)
            g_category = st.selectbox("Category (optional)", ["None"] + CATEGORIES)
            if st.form_submit_button("Add Goal", use_container_width=True):
                if not g_name.strip():
                    st.error("Goal name is required.")
                else:
                    cat_val = None if g_category == "None" else g_category
                    add_savings_goal(g_name.strip(), g_target, cat_val, g_emoji, username)
                    st.success(f"Goal '{g_name.strip()}' added!")
                    st.rerun()

    goals = get_savings_goals()

    if not goals:
        st.info("No savings goals yet. Add your first one above!")
        return

    # Chart
    st.plotly_chart(savings_goal_chart(goals), use_container_width=True)

    # Goal list
    st.subheader("Your Goals")
    for g in goals:
        pct = min(g["current_amount"] / g["target_amount"] * 100, 100.0) if g["target_amount"] > 0 else 0
        is_complete = bool(g["completed"])
        remaining = max(g["target_amount"] - g["current_amount"], 0)

        with st.container(border=True):
            top_col, status_col = st.columns([5, 1])
            with top_col:
                st.markdown(
                    f"**{g['emoji']} {g['name']}**"
                    + (f" — {g['category']}" if g.get("category") else "")
                    + (" ✅ *Completed!*" if is_complete else "")
                )
                st.progress(pct / 100, text=f"${g['current_amount']:,.2f} / ${g['target_amount']:,.2f} ({pct:.0f}%)")
                if not is_complete:
                    st.caption(f"${remaining:,.2f} left to reach your goal")
            with status_col:
                if is_complete:
                    st.markdown("✅")

            if not is_complete:
                act_col1, act_col2, act_col3 = st.columns([3, 1, 1])
                with act_col1:
                    add_amount = st.number_input(
                        "Add progress ($)", min_value=0.01, max_value=float(g["target_amount"]),
                        step=10.0, format="%.2f", key=f"progress_{g['id']}",
                    )
                with act_col2:
                    if st.button("Save", key=f"save_{g['id']}", use_container_width=True):
                        new_total = round(g["current_amount"] + add_amount, 2)
                        update_savings_goal_progress(g["id"], new_total)
                        st.success(f"+${add_amount:,.2f} added!")
                        st.rerun()
                with act_col3:
                    if st.button("Complete", key=f"complete_{g['id']}", use_container_width=True):
                        complete_savings_goal(g["id"])
                        st.success("Goal completed! 🎉")
                        st.rerun()

            del_col, _ = st.columns([1, 5])
            with del_col:
                if st.button("🗑️ Delete", key=f"delete_{g['id']}"):
                    delete_savings_goal(g["id"])
                    st.rerun()


# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    inject_pwa()
    inject_mobile_css()
    inject_romantic_css()
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
    st.sidebar.title(f"💕 Hi, {name}!")
    st.sidebar.caption("Jude loves Wincyl forever 💕")
    if date.today().day == 16:
        st.sidebar.markdown("💕 **Happy Monthsary!** 💕")
    authenticator.logout("Logout", "sidebar")

    dark_mode = st.sidebar.checkbox("🌙 Dark Mode", value=True, key="dark_mode")
    inject_dark_mode_css(dark_mode)

    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Add Expense", "Monthly View", "Analysis",
         "Search", "Budgets", "Recurring Expense", "Manage Expenses", "Savings Goals"],
    )

    pages = {
        "Dashboard": page_dashboard,
        "Add Expense": page_add_expense,
        "Monthly View": page_monthly_view,
        "Analysis": page_analysis,
        "Search": page_search,
        "Budgets": page_budgets,
        "Recurring Expense": page_recurring,
        "Manage Expenses": page_manage_expenses,
        "Savings Goals": page_savings_goals,
    }
    pages[page](username)


if __name__ == "__main__":
    main()
