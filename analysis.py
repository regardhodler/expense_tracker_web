"""Period filtering, summaries, and category analysis."""

import calendar
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

CATEGORIES = [
    "Housing", "Food", "Health", "Transportation",
    "Personal", "Entertainment", "Others",
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
    """Compute daily/weekly averages and projected month total."""
    total_so_far = sum(r["amount"] for r in rows)
    days_elapsed = max((today - month_start).days + 1, 1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    daily_avg = total_so_far / days_elapsed
    weekly_avg = daily_avg * 7
    projected_total = daily_avg * days_in_month
    return {
        "daily_avg": daily_avg,
        "weekly_avg": weekly_avg,
        "projected_total": projected_total,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "total_so_far": total_so_far,
    }


def expenses_for_day(df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    """Return expenses for a specific day."""
    if df.empty:
        return df
    mask = df["date"].dt.date == target_date
    return df[mask]


DISPLAY_NAMES = {"husband": "Jude", "wife": "Wincyl"}


def love_comparison(df: pd.DataFrame) -> tuple[pd.DataFrame, str, str, float, str, str]:
    """Compare total spending by person with romance tiers.

    The higher spender is the 'provider' (spoiling the other).
    The lower spender is the 'lover' (being spoiled).

    Returns (comp_df, lover_name, provider_name, gap_pct, love_level, message).
    """
    empty_df = pd.DataFrame(columns=["Person", "Total", "% Share"])
    if df.empty:
        return empty_df, "", "", 0.0, "soulmates", "No data yet — start spending together!"

    by_person = df.groupby("added_by")["amount"].sum().reset_index()
    by_person.columns = ["Person", "Total"]
    grand = by_person["Total"].sum()
    by_person["% Share"] = (by_person["Total"] / grand * 100).round(1) if grand > 0 else 0.0
    by_person = by_person.sort_values("Total", ascending=False)

    if len(by_person) < 2 or grand == 0:
        name = DISPLAY_NAMES.get(by_person.iloc[0]["Person"], by_person.iloc[0]["Person"])
        return by_person, name, name, 0.0, "soulmates", "Only one person spending — teamwork makes the dream work!"

    provider_user = by_person.iloc[0]["Person"]
    lover_user = by_person.iloc[1]["Person"]
    provider_name = DISPLAY_NAMES.get(provider_user, provider_user)
    lover_name = DISPLAY_NAMES.get(lover_user, lover_user)

    gap_pct = abs(by_person.iloc[0]["Total"] - by_person.iloc[1]["Total"]) / grand * 100

    if gap_pct < 5:
        love_level = "soulmates"
        message = "Perfectly balanced, like a true power couple 💪"
    elif gap_pct < 20:
        love_level = "sweet"
        message = f"{lover_name} is feeling extra loved by {provider_name} 🥰"
    elif gap_pct < 50:
        love_level = "crushing"
        message = f"{lover_name} is head over heels for {provider_name} 😍"
    else:
        love_level = "madly"
        message = f"{lover_name} is MADLY in love with {provider_name} 🔥"

    return by_person, lover_name, provider_name, gap_pct, love_level, message


# ---------------------------------------------------------------------------
# Love Points System (input-based)
# ---------------------------------------------------------------------------

LOVE_TIERS = [
    {"name": "warming_up", "emoji": "❄️", "label": "Warming Up", "min": 0},
    {"name": "sweet", "emoji": "🥰", "label": "Sweet", "min": 3},
    {"name": "crushing", "emoji": "😍", "label": "Crushing", "min": 5},
    {"name": "madly", "emoji": "🔥", "label": "Madly In Love", "min": 7},
    {"name": "soulmates", "emoji": "💪", "label": "Soulmates", "min": 10},
    {"name": "easter_egg", "emoji": "🌟", "label": "???", "min": 12},
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
    "madly": [
        "You two are basically a rom-com",
        "Netflix wants the rights to your love story",
        "The expense tracker can barely handle this much love",
        "Your love is louder than your spending",
    ],
    "soulmates": [
        "Perfectly synced — power couple confirmed",
        "10 points! You've unlocked true love",
        "Soulmate status: ACHIEVED",
        "You two are the reason love songs exist",
    ],
    "easter_egg": [
        "You broke the love meter! Scientists are baffled.",
        "ERROR 💕: Too much love detected. System overload.",
        "Achievement unlocked: LOVE BEYOND MEASURE",
        "The tracker wasn't built for this level of romance. Impressive.",
        "You've gone where no couple has gone before. Respect.",
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
