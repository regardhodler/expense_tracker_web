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
