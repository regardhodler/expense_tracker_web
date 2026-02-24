# Deploying Expense Tracker Online (Railway / Fly.io)

This guide covers deploying the expense tracker for 24/7 access using **Railway** or **Fly.io**. Both platforms support persistent volumes so your SQLite database and auth config are preserved across restarts.

## Prerequisites

1. **Git** — Initialize and push to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/expense_tracker_web.git
   git push -u origin main
   ```

2. **Environment variables** — Set these on your platform (never commit real values):
   - `COOKIE_KEY` — Random secret for session cookies (e.g. `openssl rand -hex 32`)
   - `HUSBAND_PASSWORD` — Husband's login password (optional; default: changeme123)
   - `WIFE_PASSWORD` — Wife's login password (optional; default: changeme123)

---

## Option A: Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub.
2. **New Project** → **Deploy from GitHub repo** → select your repo.
3. Railway will detect the Dockerfile and build automatically.
4. **Add a volume:**
   - Click your service → **Variables** tab
   - Under **Volumes**, add a volume with mount path: `/app/data`
5. **Set environment variables:**
   - `COOKIE_KEY` = (generate with `openssl rand -hex 32`)
   - `HUSBAND_PASSWORD` = your chosen password
   - `WIFE_PASSWORD` = your chosen password
   - `DATA_DIR` = `/app/data` (optional; default when using Docker)
6. **Settings** → generate a **public domain** for your app.
7. Redeploy if needed. Your app will be live at the generated URL.

**Note:** If you hit permission issues with the volume, try setting `RAILWAY_RUN_UID=0` (see [Railway volumes docs](https://docs.railway.app/deploy/volumes)).

---

## Option B: Fly.io

1. Install the [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/).
2. Sign in: `fly auth login`
3. **Launch the app** (creates the app; choose a region when prompted):
   ```bash
   fly launch --no-deploy
   ```
   When prompted, choose to use the existing `fly.toml` in this repo.
4. **Create a volume** in the same region you selected:
   ```bash
   fly volumes create expense_data --region YOUR_REGION --size 1
   ```
   Replace `YOUR_REGION` with e.g. `ord`, `lax`, `iad`. Run `fly platform regions` for a list.
5. **Set secrets** (use strong passwords in production):
   ```bash
   fly secrets set COOKIE_KEY=$(openssl rand -hex 32)
   fly secrets set HUSBAND_PASSWORD=your_password
   fly secrets set WIFE_PASSWORD=your_password
   ```
6. **Deploy** (the volume will be attached at `/app/data`):
   ```bash
   fly deploy
   ```
7. Open your app: `fly open` or visit the URL shown in the output.

**Troubleshooting:** If the volume mount fails, ensure the volume exists in the same region as your app. Check `fly status` and `fly volumes list`.

---

## Summary

| Platform  | Volume mount | Env vars to set                          |
|----------|--------------|------------------------------------------|
| Railway  | `/app/data`  | `COOKIE_KEY`, `HUSBAND_PASSWORD`, `WIFE_PASSWORD` |
| Fly.io   | `/app/data`  | Same (via `fly secrets set`)             |

After deployment, both you and your partner can access the app from any device with the public URL. Change the default passwords in production via the env vars above.
