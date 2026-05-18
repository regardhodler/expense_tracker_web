"""AI-powered budget insights via Anthropic Claude Haiku."""

import json
import os
from datetime import date


def _get_anthropic_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def get_anthropic_client():
    """Return an Anthropic client, or None if key is missing."""
    key = _get_anthropic_key()
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None


def call_ai(system: str, user: str, max_tokens: int = 600) -> str:
    """Call Claude Haiku and return the response text. Returns an error string on failure."""
    client = get_anthropic_client()
    if client is None:
        return (
            "⚠️ AI insights not available. "
            "Add your `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` or as an environment variable."
        )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
        )
        return response.content[0].text.strip()
    except Exception as e:
        err = str(e)
        if "api_key" in err.lower() or "authentication" in err.lower() or "unauthorized" in err.lower():
            return "⚠️ Invalid ANTHROPIC_API_KEY. Please check your key and try again."
        return f"⚠️ AI call failed: {err}"


def _system_prompt() -> str:
    today = date.today()
    return (
        f"You are a frank but kind personal finance coach for a married couple (Jude and Wincyl) living in Canada. "
        f"Today is {today.strftime('%B %d, %Y')}. All amounts are in CAD. "
        "Be concise and direct. Give practical, actionable advice. "
        "Never make up data — only reference what you are given. "
        "Avoid generic filler phrases like 'great job' or 'it looks like'. "
        "Use plain markdown (bullets, bold) so the text renders nicely in Streamlit."
    )


def build_dashboard_tip_prompt(
    month_rows: list,
    prev_month_rows: list,
    budgets: list,
) -> tuple[str, str]:
    """Returns (system, user) for a one-sentence dashboard tip."""
    month_total = round(sum(r["amount"] for r in month_rows), 2)
    prev_total = round(sum(r["amount"] for r in prev_month_rows), 2)

    cat_totals: dict[str, float] = {}
    for r in month_rows:
        cat_totals[r["category"]] = round(cat_totals.get(r["category"], 0) + r["amount"], 2)

    budget_status = [
        {
            "category": b["category"],
            "limit": b["monthly_limit"],
            "spent": round(cat_totals.get(b["category"], 0), 2),
            "over": round(cat_totals.get(b["category"], 0) - b["monthly_limit"], 2),
        }
        for b in budgets
    ]

    user_msg = json.dumps({
        "this_month_total_so_far": month_total,
        "prev_month_total": prev_total,
        "spending_by_category": cat_totals,
        "budget_status": budget_status,
    })

    system = _system_prompt() + (
        " Give EXACTLY one sentence (max 25 words) highlighting the single most notable "
        "thing about this month's spending — a win, a warning, or a key trend."
    )
    return system, user_msg


def build_analysis_insights_prompt(
    summary_df,
    total: float,
    period: str,
    canadian_df,
    prev_period_comparison_df,
) -> tuple[str, str]:
    """Returns (system, user) for the Analysis page deep insights."""
    cat_totals = {}
    if summary_df is not None and not summary_df.empty:
        for _, row in summary_df.iterrows():
            cat_totals[row["Category"]] = round(float(row["Amount"]), 2)

    cdn_comparison = []
    if canadian_df is not None and not canadian_df.empty:
        for _, row in canadian_df.iterrows():
            cdn_comparison.append({
                "category": row["Category"],
                "your_monthly_avg": round(float(row["Your Monthly Avg"]), 2),
                "canadian_avg": float(row["Canadian Avg"]),
                "pct_diff": round(float(row["% Diff"]), 1),
                "status": row["Status"],
            })

    mom_deltas = []
    if prev_period_comparison_df is not None and not prev_period_comparison_df.empty:
        for _, row in prev_period_comparison_df.iterrows():
            mom_deltas.append({
                "category": row["Category"],
                "current": round(float(row["Current"]), 2),
                "previous": round(float(row["Previous"]), 2),
                "delta_pct": round(float(row["Delta%"]), 1),
            })

    user_msg = json.dumps({
        "period": period,
        "total_spent": round(total, 2),
        "spending_by_category": cat_totals,
        "vs_canadian_averages": cdn_comparison,
        "vs_prior_period": mom_deltas,
    })

    system = _system_prompt() + (
        " Analyze the spending data and respond with:\n"
        "1. **Top overspending areas** (1-3 categories where spending is notably high vs Canadian averages or prior period)\n"
        "2. **One trend observation** (something interesting about how spending changed vs the prior period)\n"
        "3. **Two actionable suggestions** to reduce spending or reallocate budget\n"
        "Keep the whole response under 200 words. Do not repeat the raw numbers back verbatim."
    )
    return system, user_msg


def build_budget_coach_prompt(
    budgets: list,
    cat_totals_this_month: dict,
    cat_avg_by_cat: dict,
) -> tuple[str, str]:
    """Returns (system, user) for the Budget Coach advice."""
    budget_data = []
    for b in budgets:
        cat = b["category"]
        budget_data.append({
            "category": cat,
            "budget_limit": b["monthly_limit"],
            "spent_this_month": round(cat_totals_this_month.get(cat, 0), 2),
            "all_time_monthly_avg": round(cat_avg_by_cat.get(cat, 0), 2),
        })

    user_msg = json.dumps({"budgets": budget_data})

    system = _system_prompt() + (
        " Review the couple's budgets and respond with:\n"
        "1. **Budget assessment** — for each budget, note if the limit is realistic based on their historical average (too tight / about right / too loose)\n"
        "2. **One adjustment recommendation** — which budget to change and by how much\n"
        "3. **One new category suggestion** — a category worth budgeting that they haven't set yet\n"
        "Keep the whole response under 200 words."
    )
    return system, user_msg
