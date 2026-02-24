# Expense Tracker — Claude Notes

Built as a shared expense tracker for a couple (husband/wife).

## Architecture
- **Streamlit** single-page app with sidebar radio navigation
- **SQLite** single-file DB at `data/expenses.db`
- **streamlit-authenticator** (YAML-based, bcrypt passwords)
- **Plotly** for interactive charts
- **pandas** for data manipulation

## Key files
- `app.py` — main entry point, auth, all page functions
- `database.py` — SQLite CRUD (init, add, delete, query by date range)
- `analysis.py` — period date calculation, category summary, daily totals
- `visualization.py` — Plotly pie chart, bar chart, monthly trend line

## Categories (fixed)
Housing, Food, Health, Transportation, Personal, Entertainment, Others

## Auth
- Default users: husband/wife, password: changeme123
- Config auto-generated at `data/config.yaml` on first run
- Cookie-based session (30-day expiry)
