"""Period filtering, summaries, and category analysis."""

import calendar
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

CATEGORIES = [
    "Housing", "Food", "Health", "Transportation",
    "Personal", "Entertainment", "Utilities", "Others",
]

PERIOD_OPTIONS = [
    "Current month",
    "Specific month/year",
    "YTD",
    "Last 1 year",
    "Last 2 years",
    "Last 3 years",
]


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["id", "date", "amount", "category", "description", "added_by"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_period_dates(period: str, month: int | None = None, year: int | None = None) -> tuple[date, date]:
    today = date.today()
    if period == "Current month":
        return today.replace(day=1), today
    elif period == "Specific month/year" and month and year:
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = date(year, month, last_day)
        return start, min(end, today) if end > today else end
    elif period == "YTD":
        return date(today.year, 1, 1), today
    elif period == "Last 1 year":
        return today - relativedelta(years=1), today
    elif period == "Last 2 years":
        return today - relativedelta(years=2), today
    elif period == "Last 3 years":
        return today - relativedelta(years=3), today
    return today.replace(day=1), today


def category_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if df.empty:
        return pd.DataFrame(columns=["Category", "Amount", "% of Total"]), 0.0
    summary = df.groupby("category")["amount"].sum().reset_index()
    summary.columns = ["Category", "Amount"]
    total = summary["Amount"].sum()
    summary["% of Total"] = (summary["Amount"] / total * 100).round(1) if total > 0 else 0.0
    summary = summary.sort_values("Amount", ascending=False).reset_index(drop=True)
    return summary, total


def daily_totals_for_month(df: pd.DataFrame, year: int, month: int) -> dict[int, float]:
    """Return {day_number: total_spent} for a given month."""
    if df.empty:
        return {}
    mask = (df["date"].dt.year == year) & (df["date"].dt.month == month)
    monthly = df[mask]
    if monthly.empty:
        return {}
    return monthly.groupby(monthly["date"].dt.day)["amount"].sum().to_dict()


def month_comparison(current_rows: list[dict], prev_rows: list[dict]) -> tuple[pd.DataFrame, float, float]:
    """Compare spending by category between two months.

    Returns (comparison_df, current_total, previous_total).
    """
    cur_df = rows_to_dataframe(current_rows)
    prev_df = rows_to_dataframe(prev_rows)

    if cur_df.empty:
        cur_summary = pd.DataFrame(columns=["Category", "Current"])
    else:
        cur_summary = cur_df.groupby("category")["amount"].sum().reset_index()
        cur_summary.columns = ["Category", "Current"]

    if prev_df.empty:
        prev_summary = pd.DataFrame(columns=["Category", "Previous"])
    else:
        prev_summary = prev_df.groupby("category")["amount"].sum().reset_index()
        prev_summary.columns = ["Category", "Previous"]

    comparison = pd.merge(cur_summary, prev_summary, on="Category", how="outer").fillna(0)
    comparison["Delta"] = comparison["Current"] - comparison["Previous"]
    comparison["Delta%"] = comparison.apply(
        lambda r: (r["Delta"] / r["Previous"] * 100) if r["Previous"] > 0 else 0, axis=1
    ).round(1)
    comparison = comparison.sort_values("Current", ascending=False).reset_index(drop=True)

    cur_total = comparison["Current"].sum()
    prev_total = comparison["Previous"].sum()
    return comparison, cur_total, prev_total


def spending_projections(rows: list[dict], month_start: date, today: date) -> dict:
    """Compute daily/weekly averages and projected month total.

    Recurring expenses (e.g. mortgage, subscriptions) are fixed monthly costs
    paid once — they are excluded from the daily-average projection and added
    back as a flat amount so they are not multiplied across days.
    """
    recurring_rows = [r for r in rows if (r.get("description") or "").startswith("[Recurring]")]
    variable_rows  = [r for r in rows if not (r.get("description") or "").startswith("[Recurring]")]

    recurring_total = sum(r["amount"] for r in recurring_rows)
    variable_total  = sum(r["amount"] for r in variable_rows)
    total_so_far    = recurring_total + variable_total

    days_elapsed  = max((today - month_start).days + 1, 1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    # Daily/weekly averages are based on variable spending only
    daily_avg  = variable_total / days_elapsed
    weekly_avg = daily_avg * 7

    # Projection = recurring costs (once) + variable spending extrapolated to full month
    projected_total = recurring_total + daily_avg * days_in_month

    return {
        "daily_avg": daily_avg,
        "weekly_avg": weekly_avg,
        "projected_total": projected_total,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "total_so_far": total_so_far,
        "recurring_total": recurring_total,
        "variable_total": variable_total,
    }


def expenses_for_day(df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    """Return expenses for a specific day."""
    if df.empty:
        return df
    mask = df["date"].dt.date == target_date
    return df[mask]


DISPLAY_NAMES = {"husband": "Jude", "wife": "Wincyl"}



# ---------------------------------------------------------------------------
# Love Points System (input-based)
# ---------------------------------------------------------------------------

LOVE_TIERS = [
    {"name": "warming_up", "emoji": "❄️", "label": "Warming Up", "min": 0},
    {"name": "sweet", "emoji": "🥰", "label": "Sweet", "min": 3},
    {"name": "crushing", "emoji": "😍", "label": "Crushing", "min": 6},
    {"name": "lovey_dovey", "emoji": "💕", "label": "Lovey Dovey", "min": 9},
    {"name": "madly", "emoji": "🔥", "label": "Madly In Love", "min": 12},
    {"name": "on_fire", "emoji": "💘", "label": "On Fire", "min": 15},
    {"name": "inseparable", "emoji": "🫂", "label": "Inseparable", "min": 18},
    {"name": "power_couple", "emoji": "👑", "label": "Power Couple", "min": 21},
    {"name": "soulmates", "emoji": "💪", "label": "Soulmates", "min": 25},
    {"name": "easter_egg", "emoji": "🌟", "label": "???", "min": 26},
]

LOVE_MESSAGES = {
    "warming_up": [
        "The love account is empty — time to start logging!",
        "Even the longest love story starts with one expense",
        "Your wallet is shy this month... give it some love!",
        "Two hearts, zero logs — let's change that!",
    ],
    "sweet": [
        "Love is in the air... and in the spreadsheet",
        "You two are warming up nicely",
        "A few entries in, and already adorable",
        "Slowly but sweetly, love is being tracked",
    ],
    "crushing": [
        "Jude & Wincyl are on a roll!",
        "This month's love story is getting interesting",
        "Cupid called — he's taking notes",
        "You two are giving main character energy",
    ],
    "lovey_dovey": [
        "The love is getting thick in here!",
        "You two can't stop, won't stop logging love",
        "This is what peak togetherness looks like",
        "Your tracker is blushing at all this affection",
    ],
    "madly": [
        "You two are basically a rom-com",
        "Netflix wants the rights to your love story",
        "The expense tracker can barely handle this much love",
        "Your love is louder than your spending",
    ],
    "on_fire": [
        "Someone call the fire department — this love is blazing!",
        "At this rate, you'll need a bigger love meter",
        "Cupid just retired — you two don't need him anymore",
        "Your love story has more chapters than a novel",
    ],
    "inseparable": [
        "Joined at the hip and the wallet",
        "You two are practically finishing each other's expenses",
        "Separation anxiety? More like separation impossibility",
        "Even your spreadsheets are holding hands",
    ],
    "power_couple": [
        "Bow down — the power couple has arrived",
        "You two run this tracker like a Fortune 500",
        "Beyoncé and Jay-Z are taking notes",
        "Crown emoji earned. You two are royalty.",
    ],
    "soulmates": [
        "Perfectly synced — soulmate status confirmed",
        "25 points! You've unlocked true love",
        "Soulmate status: ACHIEVED",
        "You two are the reason love songs exist",
    ],
    "easter_egg": [
        "You broke the love meter! Scientists are baffled.",
        "ERROR 💕: Too much love detected. System overload.",
        "Achievement unlocked: LOVE BEYOND MEASURE",
        "The tracker wasn't built for this level of romance. Impressive.",
        "You've gone where no couple has gone before. Respect.",
        "🔞 At this point, the app suggests closing the laptop.",
        "Jude, whatever you did this month — keep doing it. 👀",
        "Wincyl said 'yes' and clearly meant it every single day.",
        "This many points means somebody is getting very lucky tonight. 😏",
        "The bedroom energy is OFF THE CHARTS. We don't make the rules.",
        "25+ points? Jude has been WORKING. Wincyl has been RECEIVING. We respect both.",
        "At this level we legally have to ask — are you two okay? Do you need water?",
        "Jude out here putting in overtime. HR would like a word.",
        "Wincyl is not logging expenses anymore, she's logging requests. 📋",
        "The neighbours called. They want you to keep it down. Or don't. We don't judge.",
        "Jude didn't come to play. Jude came to STAY. All night. Apparently.",
        "Wincyl has Jude fully trained. Points, receipts, AND performance reviews. 👑",
        "This couple has more action than a Netflix series. And better chemistry.",
        "At 25+ pts Jude is basically a full-time job with very, very good benefits.",
        "Wincyl out here collecting points AND other things. We see you. 😮‍💨",
        "Wincyl's throwing a party with the boys tonight. Jude better keep earning those points. 🎉👀",
    ],
}


def love_points(df: pd.DataFrame, year: int | None = None, month: int | None = None) -> dict:
    """Calculate love points from expense entries for the current month.

    Returns dict with: combined_points, points (per user), tier, emoji, label,
    message, next_tier_threshold.
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # Calculate points per user: 1 pt manual, 0.25 pt recurring
    user_points = {"husband": 0.0, "wife": 0.0}

    if not df.empty:
        for _, row in df.iterrows():
            user = row.get("added_by", "")
            if user not in user_points:
                continue
            desc = row.get("description", "") or ""
            if desc.startswith("[Recurring]"):
                user_points[user] += 0.25
            else:
                user_points[user] += 1.0

    combined = sum(user_points.values())

    # Determine tier (walk through tiers to find highest match)
    current_tier = LOVE_TIERS[0]
    for tier in LOVE_TIERS:
        if combined >= tier["min"]:
            current_tier = tier

    # Find next tier threshold
    tier_idx = LOVE_TIERS.index(current_tier)
    if tier_idx < len(LOVE_TIERS) - 1:
        next_threshold = LOVE_TIERS[tier_idx + 1]["min"]
    else:
        next_threshold = None  # Already at max

    # Select message deterministically
    messages = LOVE_MESSAGES[current_tier["name"]]
    msg_idx = (year * 12 + month) % len(messages)
    message = messages[msg_idx]

    return {
        "combined_points": combined,
        "points": user_points,
        "tier": current_tier["name"],
        "emoji": current_tier["emoji"],
        "label": current_tier["label"],
        "message": message,
        "next_tier_threshold": next_threshold,
    }


CANADIAN_MONTHLY_AVERAGES = {
    "Housing": 2100.00,
    "Food": 1050.00,
    "Transportation": 950.00,
    "Utilities": 350.00,
    "Health": 300.00,
    "Personal": 250.00,
    "Entertainment": 200.00,
}


def canadian_comparison(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Compare user's monthly average spending against Canadian 2-person household averages."""
    months = max((end - start).days / 30.44, 1)
    rows = []
    for cat, cdn_avg in CANADIAN_MONTHLY_AVERAGES.items():
        cat_total = df[df["category"] == cat]["amount"].sum() if not df.empty else 0
        monthly = cat_total / months
        diff = monthly - cdn_avg
        status = "✅ Below" if diff <= 0 else "⚠️ Above"
        rows.append({
            "Category": cat,
            "Your Monthly Avg": round(monthly, 2),
            "Canadian Avg": cdn_avg,
            "Difference": round(diff, 2),
            "% Diff": round(diff / cdn_avg * 100, 1),
            "Status": status,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------

def get_streaks(all_rows: list[dict]) -> dict:
    """Calculate logging streaks (current year only).

    Returns: current_streak (both users), longest_streak (both users, this year),
    jude_streak (individual), wincyl_streak (individual).
    A day counts if at least 1 manual expense (not [Recurring]) was logged.
    """
    today = date.today()
    year_start = date(today.year, 1, 1)

    husband_dates: set = set()
    wife_dates: set = set()

    for r in all_rows:
        desc = r.get("description", "") or ""
        if desc.startswith("[Recurring]"):
            continue
        raw = r.get("date", "")
        if isinstance(raw, str):
            try:
                d = date.fromisoformat(raw[:10])
            except ValueError:
                continue
        elif hasattr(raw, "date"):
            d = raw.date()
        else:
            continue
        if d < year_start:
            continue
        user = r.get("added_by", "")
        if user == "husband":
            husband_dates.add(d)
        elif user == "wife":
            wife_dates.add(d)

    combined_dates = husband_dates & wife_dates

    def _streak(dates_set: set) -> int:
        if not dates_set:
            return 0
        check = today if today in dates_set else today - timedelta(days=1)
        streak = 0
        while check >= year_start:
            if check in dates_set:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
        return streak

    def _longest(dates_set: set) -> int:
        if not dates_set:
            return 0
        longest = 0
        run = 0
        prev = None
        for d in sorted(dates_set):
            if prev is not None and (d - prev).days == 1:
                run += 1
            else:
                run = 1
            longest = max(longest, run)
            prev = d
        return longest

    return {
        "current_streak": _streak(combined_dates),
        "longest_streak": _longest(combined_dates),
        "jude_streak": _streak(husband_dates),
        "wincyl_streak": _streak(wife_dates),
    }


# ---------------------------------------------------------------------------
# Monthly challenges
# ---------------------------------------------------------------------------

def get_monthly_challenges(month_rows: list[dict], prev_month_total: float, budgets: list[dict]) -> list[dict]:
    """Define and evaluate monthly challenges."""
    manual = [r for r in month_rows if not (r.get("description", "") or "").startswith("[Recurring]")]
    jude_entries = [r for r in manual if r.get("added_by") == "husband"]
    wincyl_entries = [r for r in manual if r.get("added_by") == "wife"]
    month_total = sum(r["amount"] for r in month_rows)

    # Challenge 1: Daily Logger
    ch1_completed = len(jude_entries) > 0 and len(wincyl_entries) > 0
    ch1_pct = 100.0 if ch1_completed else (50.0 if (len(jude_entries) > 0 or len(wincyl_entries) > 0) else 0.0)
    ch1_detail = f"Jude: {len(jude_entries)} entries, Wincyl: {len(wincyl_entries)} entries"

    # Challenge 2: Budget Keeper
    cat_totals: dict = {}
    for r in month_rows:
        cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["amount"]
    over_budget = [b["category"] for b in budgets if cat_totals.get(b["category"], 0) > b["monthly_limit"]]
    ch2_completed = len(budgets) > 0 and len(over_budget) == 0
    if not budgets:
        ch2_pct = 0.0
        ch2_detail = "No budgets set yet"
    elif over_budget:
        ch2_pct = max(0.0, (len(budgets) - len(over_budget)) / len(budgets) * 100)
        ch2_detail = f"Over budget: {', '.join(over_budget)}"
    else:
        ch2_pct = 100.0
        ch2_detail = "All categories within budget! 🎉"

    # Challenge 3: Teamwork
    ch3_completed = len(jude_entries) >= 5 and len(wincyl_entries) >= 5
    ch3_pct = min((len(jude_entries) + len(wincyl_entries)) / 10 * 100, 100.0)
    ch3_detail = f"Jude: {len(jude_entries)}/5, Wincyl: {len(wincyl_entries)}/5"

    # Challenge 4: Frugal Month
    ch4_completed = prev_month_total > 0 and month_total < prev_month_total
    ch4_failed = prev_month_total > 0 and month_total >= prev_month_total
    if ch4_completed:
        ch4_pct = 100.0
    elif prev_month_total > 0 and month_total > 0:
        # Show how far over budget you are — bar fills inversely (0% = way over, approaching 100% = almost under)
        ch4_pct = max(0.0, min(prev_month_total / month_total * 100, 99.9))
    else:
        ch4_pct = 0.0
    if prev_month_total > 0:
        diff = prev_month_total - month_total
        if diff >= 0:
            ch4_detail = f"✅ ${diff:,.2f} saved vs last month (${month_total:,.2f} vs ${prev_month_total:,.2f})"
        else:
            ch4_detail = f"❌ ${abs(diff):,.2f} over last month (${month_total:,.2f} this month vs ${prev_month_total:,.2f} last month)"
    else:
        ch4_detail = "No previous month data to compare"

    # Challenge 5: Love Loggers
    total_manual = len(manual)
    ch5_pct = min(total_manual / 20 * 100, 100.0)
    ch5_completed = total_manual >= 20
    ch5_detail = f"{total_manual} / 20 combined manual entries"

    return [
        {"title": "Daily Logger", "description": "Both partners log at least 1 manual entry this month",
         "emoji": "📝", "completed": ch1_completed, "progress_pct": ch1_pct, "detail": ch1_detail},
        {"title": "Budget Keeper", "description": "All budgeted categories stay under their limit",
         "emoji": "💰", "completed": ch2_completed, "progress_pct": ch2_pct, "detail": ch2_detail},
        {"title": "Teamwork", "description": "Both partners log at least 5 manual entries each",
         "emoji": "🤝", "completed": ch3_completed, "progress_pct": ch3_pct, "detail": ch3_detail},
        {"title": "Frugal Month", "description": "Total spending is lower than the previous month",
         "emoji": "🥗", "completed": ch4_completed, "progress_pct": ch4_pct, "detail": ch4_detail},
        {"title": "Love Loggers", "description": "Combined manual entries reach 20 this month",
         "emoji": "💕", "completed": ch5_completed, "progress_pct": ch5_pct, "detail": ch5_detail},
    ]


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

def get_achievements(all_rows: list[dict]) -> list[dict]:
    """Evaluate achievement badges from all-time expense history."""
    _empty = [
        {"name": "First Entry", "emoji": "🎯", "description": "Logged first expense ever", "unlocked": False, "unlocked_date": None},
        {"name": "Century Club", "emoji": "💯", "description": "Logged 100+ total expenses", "unlocked": False, "unlocked_date": None},
        {"name": "Big Spender", "emoji": "💸", "description": "Single expense > $500", "unlocked": False, "unlocked_date": None},
        {"name": "Penny Pincher", "emoji": "🪙", "description": "An expense < $1", "unlocked": False, "unlocked_date": None},
        {"name": "Consistent Couple", "emoji": "📅", "description": "Both logged in same month for 3+ months", "unlocked": False, "unlocked_date": None},
        {"name": "Food Lovers", "emoji": "🍔", "description": "Food category > $500 in a single month", "unlocked": False, "unlocked_date": None},
        {"name": "Power Tracker", "emoji": "⚡", "description": "Logged 10+ expenses in a single day (combined)", "unlocked": False, "unlocked_date": None},
        {"name": "Year Strong", "emoji": "🏆", "description": "Expenses spanning 12+ months", "unlocked": False, "unlocked_date": None},
    ]
    if not all_rows:
        return _empty

    def _d(r) -> str:
        raw = r.get("date", "")
        return raw[:10] if isinstance(raw, str) else str(raw)[:10]

    sorted_rows = sorted(all_rows, key=_d)

    # 1. First Entry
    first_date = _d(sorted_rows[0]) if sorted_rows else None

    # 2. Century Club
    cent_unlocked = len(all_rows) >= 100
    cent_date = _d(sorted_rows[99]) if cent_unlocked else None

    # 3. Big Spender
    big = [r for r in sorted_rows if r.get("amount", 0) > 500]
    big_unlocked = bool(big)
    big_date = _d(big[0]) if big_unlocked else None

    # 4. Penny Pincher
    penny = [r for r in sorted_rows if 0 < r.get("amount", 0) < 1]
    penny_unlocked = bool(penny)
    penny_date = _d(penny[0]) if penny_unlocked else None

    # 5. Consistent Couple — both logged in same month for 3+ months
    from collections import defaultdict
    month_users: dict = defaultdict(set)
    for r in all_rows:
        ym = _d(r)[:7]
        user = r.get("added_by", "")
        if user in ("husband", "wife"):
            month_users[ym].add(user)
    both_months = sorted(m for m, u in month_users.items() if len(u) == 2)
    consistent_unlocked = len(both_months) >= 3
    consistent_date = (both_months[2] + "-01") if consistent_unlocked else None

    # 6. Food Lovers — Food > $500 in single month
    food_by_month: dict = defaultdict(float)
    food_first_row: dict = {}
    for r in sorted_rows:
        if r.get("category") == "Food":
            ym = _d(r)[:7]
            food_by_month[ym] += r.get("amount", 0)
            if ym not in food_first_row:
                food_first_row[ym] = _d(r)
    food_over = sorted([(m, t) for m, t in food_by_month.items() if t > 500])
    food_unlocked = bool(food_over)
    food_date = food_first_row.get(food_over[0][0]) if food_unlocked else None

    # 7. Power Tracker — 10+ expenses in single day
    day_counts: dict = defaultdict(int)
    for r in sorted_rows:
        day_counts[_d(r)] += 1
    power_days = sorted(d for d, c in day_counts.items() if c >= 10)
    power_unlocked = bool(power_days)
    power_date = power_days[0] if power_unlocked else None

    # 8. Year Strong — 12+ distinct months
    all_months = set(_d(r)[:7] for r in all_rows)
    year_strong_unlocked = len(all_months) >= 12
    year_strong_date = (sorted(all_months)[11] + "-01") if year_strong_unlocked else None

    return [
        {"name": "First Entry", "emoji": "🎯", "description": "Logged first expense ever",
         "unlocked": bool(sorted_rows), "unlocked_date": first_date},
        {"name": "Century Club", "emoji": "💯", "description": "Logged 100+ total expenses",
         "unlocked": cent_unlocked, "unlocked_date": cent_date},
        {"name": "Big Spender", "emoji": "💸", "description": "Single expense > $500",
         "unlocked": big_unlocked, "unlocked_date": big_date},
        {"name": "Penny Pincher", "emoji": "🪙", "description": "An expense < $1",
         "unlocked": penny_unlocked, "unlocked_date": penny_date},
        {"name": "Consistent Couple", "emoji": "📅", "description": "Both logged in same month for 3+ months",
         "unlocked": consistent_unlocked, "unlocked_date": consistent_date},
        {"name": "Food Lovers", "emoji": "🍔", "description": "Food category > $500 in a single month",
         "unlocked": food_unlocked, "unlocked_date": food_date},
        {"name": "Power Tracker", "emoji": "⚡", "description": "Logged 10+ expenses in a single day (combined)",
         "unlocked": power_unlocked, "unlocked_date": power_date},
        {"name": "Year Strong", "emoji": "🏆", "description": "Expenses spanning 12+ months",
         "unlocked": year_strong_unlocked, "unlocked_date": year_strong_date},
    ]


# ---------------------------------------------------------------------------
# Love History
# ---------------------------------------------------------------------------

def get_love_history(all_rows: list[dict]) -> list[dict]:
    """Compute love points for each past month. Returns last 12 months, oldest first."""
    if not all_rows:
        return []

    today = date.today()

    # Build set of last 12 YYYY-MM strings
    cutoff: set = set()
    for i in range(12):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        cutoff.add(f"{y:04d}-{m:02d}")

    # Find which months we have data for
    def _ym(r) -> str:
        raw = r.get("date", "")
        s = raw[:10] if isinstance(raw, str) else str(raw)[:10]
        return s[:7]

    months_in_data = set(_ym(r) for r in all_rows)
    relevant = sorted(months_in_data & cutoff)

    result = []
    for ym in relevant:
        y_val, m_val = int(ym[:4]), int(ym[5:7])
        last_day = calendar.monthrange(y_val, m_val)[1]
        m_start = f"{y_val:04d}-{m_val:02d}-01"
        m_end = f"{y_val:04d}-{m_val:02d}-{last_day:02d}"

        month_data = [
            r for r in all_rows
            if m_start <= (_ym(r) + "-01")[:10] <= m_end[:10]
            # simpler: just filter by YYYY-MM prefix
        ]
        # Actually filter properly
        month_data = [r for r in all_rows if _ym(r) == ym]

        df_m = rows_to_dataframe(month_data)
        lp = love_points(df_m, year=y_val, month=m_val)
        result.append({
            "month": date(y_val, m_val, 1).strftime("%b %Y"),
            "points": lp["combined_points"],
            "tier": lp["label"],
            "emoji": lp["emoji"],
        })

    return result


# ---------------------------------------------------------------------------
# Who spends more
# ---------------------------------------------------------------------------

def get_who_spends_more(df: pd.DataFrame) -> pd.DataFrame:
    """Per category, show Jude vs Wincyl spending."""
    if df.empty:
        return pd.DataFrame(columns=["Category", "Jude", "Wincyl", "Leader"])

    jude_totals = df[df["added_by"] == "husband"].groupby("category")["amount"].sum()
    wincyl_totals = df[df["added_by"] == "wife"].groupby("category")["amount"].sum()

    all_cats = sorted(df["category"].unique())
    rows = []
    for cat in all_cats:
        j = round(float(jude_totals.get(cat, 0)), 2)
        w = round(float(wincyl_totals.get(cat, 0)), 2)
        leader = "Jude" if j > w else ("Wincyl" if w > j else "Tied")
        rows.append({"Category": cat, "Jude": j, "Wincyl": w, "Leader": leader})

    return pd.DataFrame(rows)
