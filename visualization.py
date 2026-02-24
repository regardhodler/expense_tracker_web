"""Plotly chart builders for the expense tracker."""

import plotly.express as px
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
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=400)
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
        height=350,
        yaxis_title="Amount ($)",
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
        height=300,
    )
    return fig
