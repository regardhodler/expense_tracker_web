@echo off
:: Auto-start Expense Tracker + Cloudflare Tunnel
:: Streamlit runs minimized; tunnel exposes it publicly via HTTPS

cd /d "C:\Users\16476\expense_tracker_web"
start /min "ExpenseTracker" cmd /c ""C:\Python314\python.exe" -m streamlit run app.py --server.headless true >> "%~dp0tracker.log" 2>&1"

:: Wait for Streamlit to start before launching tunnel
timeout /t 5 /nobreak >nul

start /min "CloudflareTunnel" cmd /c ""C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8501 >> "%~dp0tunnel.log" 2>&1"
