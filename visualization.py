"""Plotly chart builders for the expense tracker."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

CATEGORY_COLORS = {
    "Housing": "#636EFA",
    "Food": "#EF553B",
    "Health": "#00CC96",
    "Transportation": "#AB63FA",
    "Personal": "#FFA15A",
    "Entertainment": "#19D3F3",
    "Utilities": "#B6E880",
    "Others": "#FF6692",
}


def pie_chart(summary_df: pd.DataFrame):
    fig = px.pie(
        summary_df,
        values="Amount",
        names="Category",
        color="Category",
        color_discrete_map=CATEGORY_COLORS,
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=500)
    return fig


def bar_chart(summary_df: pd.DataFrame):
    fig = px.bar(
        summary_df,
        x="Category",
        y="Amount",
        color="Category",
        color_discrete_map=CATEGORY_COLORS,
        text="Amount",
    )
    fig.update_traces(texttemplate="$%{text:,.2f}", textposition="outside")
    fig.update_layout(
        showlegend=False,
        margin=dict(t=30, b=20, l=20, r=20),
        height=500,
        yaxis_title="Amount ($)",
    )
    return fig


def comparison_bar_chart(comparison_df: pd.DataFrame):
    """Grouped bar chart comparing previous vs current month by category."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Previous",
        x=comparison_df["Category"],
        y=comparison_df["Previous"],
        marker_color="#6c8ebf",
        text=comparison_df["Previous"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Current",
        x=comparison_df["Category"],
        y=comparison_df["Current"],
        marker_color="#EF553B",
        text=comparison_df["Current"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        height=500,
        margin=dict(t=30, b=20, l=20, r=20),
        yaxis_title="Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def monthly_trend_chart(df: pd.DataFrame):
    """Line chart of monthly spending over time."""
    if df.empty:
        return None
    monthly = df.set_index("date").resample("ME")["amount"].sum().reset_index()
    monthly.columns = ["Month", "Amount"]
    fig = px.line(monthly, x="Month", y="Amount", markers=True)
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        margin=dict(t=20, b=20, l=20, r=20),
        height=500,
    )
    return fig



def yearly_mom_chart(monthly_totals: dict, year: int, prev_year_totals=None) -> go.Figure:
    """Bar chart of Jan–Dec spending. Green = down MoM, grey/purple = first/no data.
    Red circle marker floats above bars where spending went UP as a warning.
    Optional prior year shown as a dotted line overlay."""
    import calendar as _cal

    months = list(range(1, 13))
    month_labels = [_cal.month_abbr[m] for m in months]
    values = [monthly_totals.get(m, 0) for m in months]

    colors = []
    warning_x, warning_y = [], []
    for i in range(len(months)):
        if i == 0 or values[i - 1] == 0:
            colors.append("#c44dff")   # purple = first month / no prior data
        elif values[i] > 0 and values[i] < values[i - 1]:
            colors.append("#2ecc71")   # green = spending went down 💚
        elif values[i] > 0:
            colors.append("#ff6b9d")   # pink bar = up
            warning_x.append(month_labels[i])
            warning_y.append(values[i])   # red circle will sit at bar top

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=str(year),
        x=month_labels,
        y=values,
        marker_color=colors,
        text=[f"${v:,.0f}" if v > 0 else "" for v in values],
        textposition="outside",
        hovertemplate="%{x} " + str(year) + ": <b>$%{y:,.2f}</b><extra></extra>",
    ))

    if warning_x:
        fig.add_trace(go.Scatter(
            name="⚠️ Spending up",
            x=warning_x,
            y=warning_y,
            mode="markers",
            marker=dict(
                symbol="circle",
                size=18,
                color="rgba(255,50,50,0.15)",
                line=dict(color="#ff3232", width=2.5),
            ),
            hovertemplate="%{x}: <b>spending increased ⚠️</b><extra></extra>",
        ))

    if prev_year_totals:
        prev_values = [prev_year_totals.get(m, 0) for m in months]
        fig.add_trace(go.Scatter(
            name=str(year - 1),
            x=month_labels,
            y=prev_values,
            mode="lines+markers",
            line=dict(color="#6c8ebf", width=2, dash="dot"),
            marker=dict(size=7, color="#6c8ebf"),
            hovertemplate="%{x} " + str(year - 1) + ": <b>$%{y:,.2f}</b><extra></extra>",
        ))

    fig.update_layout(
        title=f"📅 {year} — Month-over-Month Spending (🟢 down · 🔴 up warning)",
        height=440,
        margin=dict(t=50, b=20, l=20, r=20),
        yaxis=dict(tickprefix="$", gridcolor="#2a2a4a", title="Amount ($)"),
        xaxis=dict(gridcolor="#2a2a4a"),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def canadian_comparison_chart(comp_df):
    """Grouped bar chart comparing user spending vs Canadian averages."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Your Monthly Avg",
        x=comp_df["Category"],
        y=comp_df["Your Monthly Avg"],
        marker_color="#ff6b9d",
        text=comp_df["Your Monthly Avg"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Canadian Avg",
        x=comp_df["Category"],
        y=comp_df["Canadian Avg"],
        marker_color="#6c8ebf",
        text=comp_df["Canadian Avg"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        height=500,
        margin=dict(t=30, b=20, l=20, r=20),
        yaxis_title="Monthly Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def spending_heatmap(df: pd.DataFrame, year: int, month: int) -> go.Figure:
    """GitHub-style calendar heatmap for a single month (Mon-Sun columns, weeks as rows)."""
    import calendar as _cal

    if not df.empty:
        mask = (df["date"].dt.year == year) & (df["date"].dt.month == month)
        daily = df[mask].groupby(df[mask]["date"].dt.day)["amount"].sum().to_dict()
    else:
        daily = {}

    cal_obj = _cal.Calendar(firstweekday=0)  # Monday first
    weeks = cal_obj.monthdayscalendar(year, month)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    z, text_vals = [], []
    for week in weeks:
        row_z, row_t = [], []
        for day in week:
            if day == 0:
                row_z.append(None)
                row_t.append("")
            else:
                amt = daily.get(day, 0)
                row_z.append(amt if amt > 0 else 0)
                row_t.append(f"<b>Day {day}</b><br>${amt:,.2f}" if amt > 0 else f"<b>Day {day}</b><br>$0.00")
        z.append(row_z)
        text_vals.append(row_t)

    colorscale = [
        [0.0, "#1e1e2e"],
        [0.001, "#2d1b3d"],
        [0.3, "#9b3dc8"],
        [0.6, "#c44dff"],
        [1.0, "#ff6b9d"],
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=day_labels,
        text=text_vals,
        hoverinfo="text",
        colorscale=colorscale,
        showscale=True,
        colorbar=dict(title="$", tickprefix="$"),
        zmin=0,
        xgap=4,
        ygap=4,
    ))

    month_name = _cal.month_name[month]
    fig.update_layout(
        title=f"📅 {month_name} {year} — Daily Spending",
        height=max(200, 80 + len(weeks) * 55),
        margin=dict(t=45, b=20, l=20, r=80),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(weeks))),
            ticktext=[f"Wk {i + 1}" for i in range(len(weeks))],
            showgrid=False,
            autorange="reversed",
        ),
        xaxis=dict(showgrid=False),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
    )
    return fig


def love_history_chart(history: list[dict]) -> go.Figure:
    """Line chart of combined love points over past months with tier reference lines."""
    if not history:
        return go.Figure()

    months = [h["month"] for h in history]
    points = [h["points"] for h in history]
    emojis = [h["emoji"] for h in history]

    tier_thresholds = [
        (3, "🥰 Sweet"), (6, "😍 Crushing"), (9, "💕 Lovey Dovey"),
        (12, "🔥 Madly In Love"), (15, "💘 On Fire"),
        (18, "🫂 Inseparable"), (21, "👑 Power Couple"), (25, "💪 Soulmates"),
    ]

    fig = go.Figure()

    max_pts = max(points) if points else 10
    for threshold, label in tier_thresholds:
        if threshold <= max_pts + 6:
            fig.add_hline(
                y=threshold, line_dash="dot", line_color="#444",
                annotation_text=label, annotation_position="right",
                annotation_font_size=9, annotation_font_color="#888",
            )

    n = len(points)
    marker_colors = [
        f"rgb({int(255 - i / max(n - 1, 1) * (255 - 196))},{int(107 + i / max(n - 1, 1) * (68 - 107))},{int(157 + i / max(n - 1, 1) * (255 - 157))})"
        for i in range(n)
    ]

    fig.add_trace(go.Scatter(
        x=months,
        y=points,
        mode="lines+markers+text",
        text=[f"{e} {p:.1f}" for e, p in zip(emojis, points)],
        textposition="top center",
        textfont=dict(size=11),
        line=dict(color="#ff6b9d", width=3),
        marker=dict(size=11, color=marker_colors, line=dict(color="#fff", width=1)),
        name="Love Points",
        hovertemplate="%{x}: <b>%{y:.1f} pts</b><extra></extra>",
    ))

    fig.update_layout(
        title="📈 Love Points History",
        xaxis_title="Month",
        yaxis_title="Combined Love Points",
        height=380,
        margin=dict(t=45, b=30, l=30, r=100),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2a2a4a"),
        yaxis=dict(gridcolor="#2a2a4a", rangemode="tozero"),
    )
    return fig


def who_spends_more_chart(df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: Jude (blue) vs Wincyl (pink) per category."""
    if df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="💙 Jude",
        x=df["Category"],
        y=df["Jude"],
        marker_color="#4a8cff",
        text=df["Jude"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="💗 Wincyl",
        x=df["Category"],
        y=df["Wincyl"],
        marker_color="#ff6b9d",
        text=df["Wincyl"].map("${:,.0f}".format),
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        title="💰 Who Spends More Per Category",
        height=420,
        margin=dict(t=45, b=20, l=20, r=20),
        yaxis_title="Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        xaxis=dict(gridcolor="#2a2a4a"),
        yaxis=dict(gridcolor="#2a2a4a"),
    )
    return fig


def savings_goal_chart(goals: list[dict]) -> go.Figure:
    """Horizontal bar chart showing progress for each savings goal."""
    if not goals:
        return go.Figure()

    names = [f"{g['emoji']} {g['name']}" for g in goals]
    current = [g["current_amount"] for g in goals]
    target = [g["target_amount"] for g in goals]
    bar_colors = ["#2ecc71" if g["completed"] else "#ff9800" for g in goals]

    labels = []
    for g in goals:
        if g["target_amount"] > 0:
            pct = min(g["current_amount"] / g["target_amount"] * 100, 100.0)
            labels.append(f"${g['current_amount']:,.0f} / ${g['target_amount']:,.0f} ({pct:.0f}%)")
        else:
            labels.append(f"${g['current_amount']:,.0f}")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names, x=target, orientation="h",
        marker_color="rgba(255,255,255,0.08)",
        marker_line=dict(color="rgba(255,255,255,0.3)", width=1),
        name="Target", showlegend=True,
        hovertemplate="Target: $%{x:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=names, x=current, orientation="h",
        marker_color=bar_colors,
        text=labels,
        textposition="outside",
        name="Saved", showlegend=True,
        hovertemplate="Saved: $%{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        barmode="overlay",
        title="🎯 Savings Goals Progress",
        height=max(200, 80 + len(goals) * 55),
        margin=dict(t=45, b=20, l=20, r=140),
        xaxis_title="Amount ($)",
        xaxis=dict(tickprefix="$", gridcolor="#2a2a4a"),
        yaxis=dict(gridcolor="#2a2a4a"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
    )
    return fig


def jueds_monthly_chart(monthly_data: list[dict]) -> go.Figure:
    """Grouped bar chart (Net Income / Recurring / Manual) + Free Cash Flow line."""
    labels = [d["month_label"] for d in monthly_data]
    net_income = [d["net_income"] for d in monthly_data]
    recurring = [d["recurring_expense"] for d in monthly_data]
    manual = [d["manual_expense"] for d in monthly_data]
    fcf = [d["free_cash_flow"] for d in monthly_data]
    fcf_colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in fcf]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Net Income", x=labels, y=net_income,
                         marker_color="#3498db", opacity=0.85))
    fig.add_trace(go.Bar(name="Recurring Expense", x=labels, y=recurring,
                         marker_color="#e67e22", opacity=0.85))
    fig.add_trace(go.Bar(name="Manual Expense", x=labels, y=manual,
                         marker_color="#e74c3c", opacity=0.85))
    fig.add_trace(go.Scatter(name="Free Cash Flow", x=labels, y=fcf,
                             mode="lines+markers",
                             line=dict(color="#888888", width=2),
                             marker=dict(color=fcf_colors, size=8)))
    fig.update_layout(
        barmode="group",
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig
