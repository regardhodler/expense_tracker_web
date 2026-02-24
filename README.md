# Expense Tracker

A shared expense tracker for couples, built with Streamlit + SQLite.

## Setup

```bash
cd expense_tracker_web
pip install -r requirements.txt
```

## Run

```bash
python -m streamlit run app.py
```

Open http://localhost:8501 in your browser.

**On your phone (same WiFi):** Find your computer's local IP (e.g. `ipconfig` on Windows) and open `http://<your-ip>:8501`.

## Default Credentials

| Username | Password      |
|----------|---------------|
| husband  | changeme123   |
| wife     | changeme123   |

The config file (`data/config.yaml`) is auto-generated on first run. To change passwords, edit the YAML (re-hash with bcrypt) or delete `data/config.yaml` to regenerate defaults.

## Features

- **Dashboard** — month total, YTD total, recent expenses, spending trend
- **Add Expense** — date, amount, category, description
- **Monthly View** — calendar grid with daily totals, category breakdown
- **Analysis** — period selection, category summary, pie/bar charts, trend line, spending warnings
- **Delete Expense** — find and remove incorrect entries

## Categories

Housing, Food, Health, Transportation, Personal, Entertainment, Others

## Backup

Just copy `data/expenses.db`. It's a single SQLite file.

## Remote Access (24/7 hosting)

For always-on access from anywhere, see **[DEPLOYMENT.md](DEPLOYMENT.md)** for step-by-step instructions to deploy on **Railway** or **Fly.io** with persistent storage. Both options use the included Dockerfile and keep your SQLite database and auth config intact.

**Security note:** This app uses simple cookie-based auth suitable for home/LAN use. When deploying online, set strong `COOKIE_KEY`, `HUSBAND_PASSWORD`, and `WIFE_PASSWORD` via environment variables (see DEPLOYMENT.md).
