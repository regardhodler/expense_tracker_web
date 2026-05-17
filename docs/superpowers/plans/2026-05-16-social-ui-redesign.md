# Social UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the expense tracker UI with a Facebook-style social feel — card-based feed, partner profile mini-cards, bottom nav, emoji reactions, mobile-first layout, and 7 easter eggs.

**Architecture:** New `styles.py` provides all HTML/CSS component templates. New DB tables (`reactions`, `easter_egg_state`) in `database.py`. `app.py` routing switches from sidebar radio to `st.query_params`. All pages rewritten to use card-based layout. No new Python dependencies.

**Tech Stack:** Python, Streamlit 1.31+ (`@st.dialog`), SQLite, Plotly, pandas, inline HTML/CSS/JS via `unsafe_allow_html`

**Spec:** `docs/superpowers/specs/2026-05-16-social-ui-redesign-design.md`

---

## Chunk 1: Foundation — DB Tables + styles.py

**Files:**
- Modify: `database.py` (add `reactions` and `easter_egg_state` table init + CRUD)
- Create: `styles.py` (all HTML/CSS component functions and copy constants)
- Modify: `tests/test_analysis.py` (add smoke tests for styles functions)

---

### Task 1: Add DB tables and CRUD to `database.py`

**Files:**
- Modify: `database.py`

- [ ] **Step 1: Find `init_db()` in `database.py` and add two new table definitions inside it**

Add after the existing `CREATE TABLE IF NOT EXISTS` statements:

```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_id INTEGER NOT NULL,
        reacted_by TEXT NOT NULL,
        emoji TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS easter_egg_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
""")
```

- [ ] **Step 2: Add CRUD functions at the bottom of `database.py`**

```python
# --- Reactions ---

def add_reaction(expense_id: int, reacted_by: str, emoji: str) -> None:
    """Toggle reaction: add if not present, remove if already reacted with same emoji."""
    from datetime import datetime
    conn = _get_conn()
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM reactions WHERE expense_id=? AND reacted_by=? AND emoji=?",
        (expense_id, reacted_by, emoji)
    ).fetchone()
    if existing:
        cur.execute("DELETE FROM reactions WHERE id=?", (existing[0],))
    else:
        cur.execute(
            "INSERT INTO reactions (expense_id, reacted_by, emoji, created_at) VALUES (?,?,?,?)",
            (expense_id, reacted_by, emoji, datetime.utcnow().isoformat())
        )
    conn.commit()


def get_reactions(expense_ids: list[int]) -> dict[int, list[dict]]:
    """Return {expense_id: [{"reacted_by": ..., "emoji": ...}, ...]} for the given ids."""
    if not expense_ids:
        return {}
    conn = _get_conn()
    placeholders = ",".join("?" * len(expense_ids))
    rows = conn.execute(
        f"SELECT expense_id, reacted_by, emoji FROM reactions WHERE expense_id IN ({placeholders})",
        expense_ids
    ).fetchall()
    result: dict = {}
    for expense_id, reacted_by, emoji in rows:
        result.setdefault(expense_id, []).append({"reacted_by": reacted_by, "emoji": emoji})
    return result


# --- Easter Egg State ---

def get_easter_egg(key: str, default: str = "0") -> str:
    """Read a value from easter_egg_state. Returns default if key not found."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM easter_egg_state WHERE key=?", (key,)
    ).fetchone()
    return row[0] if row else default


def set_easter_egg(key: str, value: str) -> None:
    """Upsert a key in easter_egg_state."""
    from datetime import datetime
    conn = _get_conn()
    conn.execute(
        "INSERT INTO easter_egg_state (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, datetime.utcnow().isoformat())
    )
    conn.commit()
```

- [ ] **Step 3: Run existing tests to verify no regressions**

```
pytest tests/ -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add database.py
git commit -m "feat(db): add reactions and easter_egg_state tables with CRUD"
```

---

### Task 2: Create `styles.py` — constants and component functions

**Files:**
- Create: `styles.py`

- [ ] **Step 1: Create `styles.py` with constants**

```python
"""HTML/CSS component library for the expense tracker social UI."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Copy constants
# ---------------------------------------------------------------------------

FORTUNE_MESSAGES: list[str] = [
    "A couple that budgets together, stays together 💕",
    "Your wallet thanks you. Your heart thanks you more. 🌹",
    "Frugality is just romance with a spreadsheet. 📊",
    "Every dollar saved is a future adventure funded. ✈️",
    "Love is patient, love is kind, love also tracks receipts. 🧾",
    "You logged an expense. Somewhere, a financial advisor smiled. 📈",
    "Money can't buy happiness, but it can buy groceries. 🛒",
    "This entry has been blessed by the Budget Gods. 🙏",
    "Tracking expenses: cheaper than couples therapy. 💸",
    "Behind every great couple is a great spreadsheet. 📋",
    "The best things in life are free. The rest need to be categorized. 🏷️",
    "A penny logged is a penny understood. 🪙",
    "You're doing great. Financially and emotionally. 💪",
    "Jude and Wincyl, keeping the receipts of love. 💕",
    "This expense has been approved by the Department of Us. ✅",
    "Your future selves will thank you for this entry. ⏰",
    "Fortune favors the one who tracks. 🔮",
    "Romance + spreadsheets = power couple. 👑",
    "Somewhere, your bank account is smiling. 🏦",
    "Logged. Sealed. Delivered. We're yours. 💌",
]

CATEGORY_FUN_FACTS: dict[str, str] = {
    "Housing": "Your home is your castle — and usually your biggest budget line. 🏰 The average Canadian couple spends $2,100/month on housing.",
    "Food": "Fun fact: the average Canadian couple spends ~$1,050/month on food. You're feeding love! 🍔",
    "Health": "Investing in health now saves on costs later. You're literally buying more time together. 💪",
    "Transportation": "Canadians spend ~$950/month getting around. Every trip is a chance for a mini adventure. 🚗",
    "Personal": "Personal spending is self-care — and self-care makes you a better partner. 💅",
    "Entertainment": "Entertainment expenses = memories made. Worth every dollar. 🎬",
    "Others": "The 'Others' category — the mystery box of budgeting. 📦",
}

COUPLE_STATS_LABELS: list[str] = [
    "Most expensive single day ever 💸",
    "Biggest food month 🍔",
    "Longest streak ever 🔥",
    "Total expenses logged together 💕",
    "Most used category of all time 📦",
    "Highest single expense 💎",
    "Most active month 📅",
]

REACTION_EMOJIS: list[str] = ["💕", "❤️", "😂", "😮"]
```

- [ ] **Step 2: Add `global_css()` to `styles.py`**

```python
# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

def global_css() -> str:
    """CSS injected once at app startup: sidebar hide, bottom nav spacing, card styles, breakpoints."""
    return """
<style>
/* Hide Streamlit default sidebar */
section[data-testid="stSidebar"] { display: none !important; }

/* Reserve space at bottom for nav bar on mobile */
@media (max-width: 768px) {
    .main .block-container { padding-bottom: 80px !important; }
}

/* Expense card */
.exp-card {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    border: 1px solid #2a2a4a;
}
.exp-card:hover { border-color: #c44dff44; }

/* Avatar circle */
.avatar {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #ff6b9d, #c44dff);
    display: flex; align-items: center; justify-content: center;
    font-weight: bold; color: #fff; font-size: 0.85em;
    flex-shrink: 0;
}

/* Profile mini-card */
.profile-card {
    background: #1a1a2e;
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #2a2a4a;
    text-align: center;
}

/* Bottom nav */
.bottom-nav {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
    background: #111122;
    border-top: 1px solid #2a2a4a;
    display: flex; justify-content: space-around; align-items: center;
    padding: 8px 0 12px;
}
.bottom-nav a {
    text-decoration: none; color: #666;
    display: flex; flex-direction: column; align-items: center;
    font-size: 0.6em; gap: 2px;
}
.bottom-nav a.active { color: #c44dff; }
.bottom-nav .nav-icon { font-size: 1.6em; line-height: 1; }
.fab {
    background: linear-gradient(135deg, #ff6b9d, #c44dff);
    border-radius: 50%; width: 48px; height: 48px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.4em; margin-top: -16px;
    box-shadow: 0 4px 16px #c44dff55;
    text-decoration: none !important;
}

/* App header */
.app-header {
    background: #111122;
    border-bottom: 1px solid #2a2a4a;
    padding: 10px 16px;
    display: flex; justify-content: space-between; align-items: center;
    position: sticky; top: 0; z-index: 999;
    margin-bottom: 16px;
}
.app-header .brand { color: #ff6b9d; font-weight: bold; font-size: 1.1em; }
.app-header .header-right { display: flex; align-items: center; gap: 12px; }
.notif-bell { color: #c44dff; font-size: 1.2em; position: relative; cursor: pointer; }
.notif-badge {
    position: absolute; top: -4px; right: -6px;
    background: #ff6b9d; color: #fff;
    border-radius: 50%; width: 14px; height: 14px;
    font-size: 0.55em; display: flex; align-items: center; justify-content: center;
}
.user-avatar {
    width: 30px; height: 30px; border-radius: 50%;
    background: linear-gradient(135deg, #ff6b9d, #c44dff);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8em; font-weight: bold; color: #fff;
}

/* Dialog slide-up on mobile */
@media (max-width: 768px) {
    div[data-testid="stDialog"] > div {
        position: fixed !important; bottom: 0 !important; left: 0 !important;
        right: 0 !important; top: auto !important;
        border-radius: 16px 16px 0 0 !important;
        max-height: 85vh !important;
    }
}

/* Confetti overlay */
@keyframes confetti-fall {
    0% { transform: translateY(-10px) rotate(0deg); opacity: 1; }
    100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
}
.confetti-piece {
    position: fixed; top: -10px; font-size: 1.4em;
    animation: confetti-fall 2.5s ease-in forwards;
    z-index: 99999; pointer-events: none;
}
</style>
"""
```

- [ ] **Step 3: Add component functions to `styles.py`**

```python
# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

import random
from datetime import datetime, timezone


def app_header(username: str, notif_count: int = 0) -> str:
    """Branded top header. username = 'husband' | 'wife'."""
    initial = "J" if username == "husband" else "W"
    bell = (
        f'<span class="notif-bell" id="love-logo" onclick="handleLogoPing()">'
        f'💕<span class="notif-badge">{notif_count}</span></span>'
        if notif_count > 0
        else '<span class="notif-bell" id="love-logo" onclick="handleLogoPing()">💕</span>'
    )
    return f"""
<div class="app-header">
  <span class="brand">💕 FamilyLedger</span>
  <div class="header-right">
    {bell}
    <div class="user-avatar">{initial}</div>
  </div>
</div>
<script>
var _logoPings = 0;
function handleLogoPing() {{
    _logoPings++;
    if (_logoPings >= 5) {{
        _logoPings = 0;
        document.getElementById('couple-stats-panel').style.display = 'block';
    }}
}}
</script>
"""


def bottom_nav(active_page: str) -> str:
    """Fixed bottom nav bar. active_page: 'home'|'feed'|'add'|'rewards'|'more'."""
    def _cls(page: str) -> str:
        return "active" if active_page == page else ""

    return f"""
<nav class="bottom-nav">
  <a href="?page=home" class="{_cls('home')}">
    <span class="nav-icon">🏠</span>Home
  </a>
  <a href="?page=feed" class="{_cls('feed')}">
    <span class="nav-icon">📰</span>Feed
  </a>
  <a href="?page=add" class="fab">➕</a>
  <a href="?page=rewards" class="{_cls('rewards')}">
    <span class="nav-icon">🏆</span>Rewards
  </a>
  <a href="?page=more" class="{_cls('more')}">
    <span class="nav-icon">☰</span>More
  </a>
</nav>
"""


def card_expense(row: dict, reactions: list[dict], current_user: str) -> str:
    """Single expense card. row = DB row dict. reactions = list of reaction dicts. current_user = 'husband'|'wife'."""
    _DISPLAY = {"husband": "Jude", "wife": "Wincyl"}
    added_by = row.get("added_by", "")
    initial = "J" if added_by == "husband" else "W"
    display_name = _DISPLAY.get(added_by, added_by)
    desc = row.get("description", "") or ""
    is_recurring = desc.startswith("[Recurring]")
    badge = '<span style="font-size:0.7em;background:#2a2a4a;padding:2px 6px;border-radius:8px">🔄 Recurring</span>' if is_recurring else ""
    clean_desc = desc.replace("[Recurring] ", "") if is_recurring else desc

    CATEGORY_EMOJI = {
        "Housing": "🏠", "Food": "🍔", "Health": "💊",
        "Transportation": "🚗", "Personal": "💅",
        "Entertainment": "🎬", "Others": "📦",
    }
    cat = row.get("category", "Others")
    cat_emoji = CATEGORY_EMOJI.get(cat, "📦")

    # Time ago
    raw_date = str(row.get("date", ""))[:10]
    try:
        from datetime import date as _date
        exp_date = _date.fromisoformat(raw_date)
        delta = (_date.today() - exp_date).days
        if delta == 0:
            time_str = "Today"
        elif delta == 1:
            time_str = "Yesterday"
        else:
            time_str = f"{delta}d ago"
    except Exception:
        time_str = raw_date

    # Reaction counts
    reaction_counts: dict[str, int] = {}
    user_reacted: set[str] = set()
    for r in reactions:
        reaction_counts[r["emoji"]] = reaction_counts.get(r["emoji"], 0) + 1
        if r["reacted_by"] == current_user:
            user_reacted.add(r["emoji"])

    reaction_html = ""
    for emoji in REACTION_EMOJIS:
        count = reaction_counts.get(emoji, 0)
        active_style = "background:#c44dff22;border-color:#c44dff;" if emoji in user_reacted else ""
        count_str = f" {count}" if count > 0 else ""
        reaction_html += (
            f'<span style="cursor:pointer;padding:3px 7px;border-radius:12px;'
            f'border:1px solid #333;font-size:0.8em;{active_style}">'
            f'{emoji}{count_str}</span>'
        )

    expense_id = row.get("id", 0)
    return f"""
<div class="exp-card" data-expense-id="{expense_id}">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
    <div class="avatar">{initial}</div>
    <div>
      <div style="font-weight:bold;color:#e0e0e0;font-size:0.9em">{display_name} {badge}</div>
      <div style="color:#666;font-size:0.72em">{time_str}</div>
    </div>
  </div>
  <div style="font-size:1.15em;font-weight:bold;color:#ff6b9d">{cat_emoji} ${row.get('amount', 0):,.2f} <span style="color:#888;font-weight:normal;font-size:0.8em">{cat}</span></div>
  {f'<div style="color:#aaa;font-size:0.82em;margin-top:4px">{clean_desc}</div>' if clean_desc else ''}
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px">{reaction_html}</div>
</div>
"""


def card_profile(user: str, stats: dict) -> str:
    """Partner profile mini-card. stats = {total, streak, tier_emoji, tier_label, top_category}."""
    _DISPLAY = {"husband": "Jude", "wife": "Wincyl"}
    initial = "J" if user == "husband" else "W"
    name = _DISPLAY.get(user, user)
    total = stats.get("total", 0.0)
    streak = stats.get("streak", 0)
    tier_emoji = stats.get("tier_emoji", "❄️")
    tier_label = stats.get("tier_label", "Warming Up")
    top_cat = stats.get("top_category", "")
    return f"""
<div class="profile-card">
  <div class="avatar" style="margin:0 auto 8px">{initial}</div>
  <div style="font-weight:bold;color:#e0e0e0">{name}</div>
  <div style="font-size:1.3em;font-weight:bold;color:#ff6b9d;margin:4px 0">${total:,.2f}</div>
  <div style="color:#888;font-size:0.75em">{tier_emoji} {tier_label}</div>
  {f'<div style="color:#666;font-size:0.72em;margin-top:4px">🔥 {streak} day streak</div>' if streak > 0 else ''}
  {f'<div style="color:#666;font-size:0.72em">{top_cat}</div>' if top_cat else ''}
</div>
"""


def confetti_burst() -> str:
    """Self-contained confetti animation. Auto-removes after 2.5s."""
    pieces = ""
    emojis = ["🎊", "🎉", "💕", "✨", "🌟", "💖", "🎈"]
    for i in range(20):
        left = random.randint(0, 100)
        delay = round(random.uniform(0, 1.2), 2)
        emoji = emojis[i % len(emojis)]
        pieces += f'<div class="confetti-piece" style="left:{left}vw;animation-delay:{delay}s">{emoji}</div>\n'
    return f"""
<div id="confetti-container">{pieces}</div>
<script>setTimeout(function(){{
    var c = document.getElementById('confetti-container');
    if (c) c.remove();
}}, 3500);</script>
"""


def easter_egg_fortune(message: str) -> str:
    """Fortune cookie toast. Appears for 4s then fades."""
    return f"""
<div id="fortune-toast" style="
    position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
    background:linear-gradient(135deg,#1a1a2e,#2a1a3e);
    border:1px solid #c44dff;border-radius:12px;
    padding:12px 20px;max-width:320px;text-align:center;
    color:#e0e0e0;font-size:0.85em;z-index:99998;
    box-shadow:0 4px 20px #c44dff44;
    animation:toast-fade 4s ease forwards;
">
🥠 {message}
</div>
<style>
@keyframes toast-fade {{
    0% {{ opacity:0; transform:translateX(-50%) translateY(10px); }}
    15% {{ opacity:1; transform:translateX(-50%) translateY(0); }}
    75% {{ opacity:1; }}
    100% {{ opacity:0; }}
}}
</style>
<script>setTimeout(function(){{
    var t = document.getElementById('fortune-toast');
    if (t) t.remove();
}}, 4200);</script>
"""


def sync_banner() -> str:
    """'Sync'd!' surprise banner shown when both partners logged today."""
    return """
<div style="
    background:linear-gradient(135deg,#1a3a2a,#2a1a3e);
    border:1px solid #c44dff;border-radius:12px;
    padding:14px 18px;margin:10px 0;
    display:flex;align-items:center;gap:12px;
    animation:sync-pop 0.4s cubic-bezier(0.34,1.56,0.64,1);
">
  <span style="font-size:2em">✨</span>
  <div>
    <div style="color:#c44dff;font-weight:bold">Sync'd Today!</div>
    <div style="color:#aaa;font-size:0.82em">Both of you logged expenses today. You're in sync! 💕</div>
  </div>
</div>
<style>
@keyframes sync-pop {{
    from {{ transform: scale(0.85); opacity: 0; }}
    to {{ transform: scale(1); opacity: 1; }}
}}
</style>
"""
```

- [ ] **Step 4: Run a quick import smoke test**

```
python -c "import styles; print('styles.py OK'); print(len(styles.FORTUNE_MESSAGES), 'fortune messages')"
```

Expected output:
```
styles.py OK
20 fortune messages
```

- [ ] **Step 5: Commit**

```bash
git add styles.py
git commit -m "feat(styles): add component library with nav, cards, easter egg components"
```

---

## Chunk 2: Navigation Routing

**Files:**
- Modify: `app.py` (replace sidebar radio with query_params routing + inject header + bottom nav)

---

### Task 3: Replace sidebar routing with query_params

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `styles` import at the top of `app.py`**

Find the existing imports block and add:
```python
import styles
```

- [ ] **Step 2: Find the main routing block in `app.py`**

Look for the `st.sidebar` navigation (sidebar radio or selectbox, likely near the bottom of the file around the `if __name__` block or the top-level `main()` function). It will look something like:
```python
page = st.sidebar.radio("Navigate", ["Dashboard", "Add Expense", ...])
```
or a `st.sidebar.selectbox`.

- [ ] **Step 3: Replace the entire navigation block with query_params routing**

Remove the sidebar navigation entirely. Replace with:

```python
def main():
    # Inject global CSS (hides sidebar, sets up card styles, bottom nav)
    st.markdown(styles.global_css(), unsafe_allow_html=True)

    # Auth check — keep existing authenticator logic unchanged above this
    # (do not touch the authenticator block)

    username = st.session_state.get("username", "")

    # Inject app header
    st.markdown(styles.app_header(username), unsafe_allow_html=True)

    # Routing
    PAGE_MAP = {
        "home": page_dashboard,
        "feed": page_feed,
        "add": page_add_expense,
        "rewards": page_rewards,
        "more": page_more,
        "analysis": page_analysis,
        "search": page_search,
        "budgets": page_budgets,
        "monthly": page_monthly_view,
    }
    raw_page = st.query_params.get("page", "home")
    page_key = raw_page if raw_page in PAGE_MAP else "home"

    # Render page
    PAGE_MAP[page_key](username)

    # Inject bottom nav (after page content)
    st.markdown(styles.bottom_nav(page_key), unsafe_allow_html=True)
```

> **Note:** `"add": page_add_expense` in PAGE_MAP is temporary. Chunk 4 overrides it so the FAB opens a dialog instead. The app is functional at this stage — clicking ➕ navigates to the full add page, which is correct interim behavior.

- [ ] **Step 4: Create stub `page_more()` function (the "More" page)**

Add this function to `app.py` (near the other page functions):

```python
def page_more(username: str):
    st.header("More")
    st.markdown("**Navigation**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💰 Budgets", use_container_width=True):
            st.query_params["page"] = "budgets"
            st.rerun()
        if st.button("🔍 Search", use_container_width=True):
            st.query_params["page"] = "search"
            st.rerun()
    with col2:
        if st.button("📅 Monthly View", use_container_width=True):
            st.query_params["page"] = "monthly"
            st.rerun()
        if st.button("📊 Analysis", use_container_width=True):
            st.query_params["page"] = "analysis"
            st.rerun()
```

- [ ] **Step 5: Create stub `page_feed()` function (filled out in Chunk 3)**

```python
def page_feed(username: str):
    st.header("📰 Feed")
    st.info("Feed coming soon...")
```

- [ ] **Step 6: Smoke test — start the app and verify navigation works**

```
streamlit run app.py
```

- Open http://localhost:8501
- Click each bottom nav tab — URL should change to `?page=home`, `?page=feed`, etc.
- Sidebar should be hidden.
- Header should appear at top with 💕 FamilyLedger.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat(nav): replace sidebar radio with query_params bottom nav routing"
```

---

## Chunk 3: Feed Page + Expense Cards + Profile Mini-Cards

**Files:**
- Modify: `app.py` (`page_feed`, `page_dashboard` profile cards section)
- Modify: `database.py` (verify `get_reactions` is importable)

---

### Task 4: Implement `page_feed()` with card layout

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Confirm required functions are already imported in `app.py`**

These must already be imported (they exist in the current codebase):
- `_cached_all_expenses()` — defined in `app.py` itself (around line 57)
- `rows_to_dataframe`, `love_points`, `get_streaks` — imported from `analysis`
- `timedelta` — from Python's `datetime`

Run a quick check:
```
python -c "import app" 2>&1 | head -5
```
Expected: no import errors.

- [ ] **Step 2: Add `get_reactions` to the `database.py` imports at the top of `app.py`**

Find the `from database import (...)` block and add `get_reactions`.

- [ ] **Step 2: Replace the stub `page_feed()` with the full implementation**

```python
def page_feed(username: str):
    st.header("📰 Feed")

    all_rows = _cached_all_expenses()
    if not all_rows:
        st.info("No expenses yet — add your first one! 💕")
        return

    # Sort newest first
    sorted_rows = sorted(all_rows, key=lambda r: str(r.get("date", ""))[:10], reverse=True)

    # Pagination
    PAGE_SIZE = 20
    offset = st.session_state.get("feed_offset", 0)
    page_rows = sorted_rows[offset: offset + PAGE_SIZE]

    # Fetch reactions for this page
    expense_ids = [r["id"] for r in page_rows if "id" in r]
    reactions_map = get_reactions(expense_ids)

    # Group by Today / Yesterday / Past
    from datetime import date as _date
    today_str = str(_date.today())
    yesterday_str = str(_date.today() - timedelta(days=1))

    groups: dict[str, list] = {"Today": [], "Yesterday": [], "Past": []}
    for row in page_rows:
        d = str(row.get("date", ""))[:10]
        if d == today_str:
            groups["Today"].append(row)
        elif d == yesterday_str:
            groups["Yesterday"].append(row)
        else:
            groups["Past"].append(row)

    for group_name, group_rows in groups.items():
        if not group_rows:
            continue
        st.markdown(f"**{group_name}**")
        for row in group_rows:
            expense_id = row.get("id", 0)
            row_reactions = reactions_map.get(expense_id, [])
            st.markdown(
                styles.card_expense(row, row_reactions, username),
                unsafe_allow_html=True,
            )
            # Reaction buttons (st.button fallback — one row per expense)
            react_cols = st.columns(len(styles.REACTION_EMOJIS))
            for j, emoji in enumerate(styles.REACTION_EMOJIS):
                with react_cols[j]:
                    count = sum(1 for r in row_reactions if r["emoji"] == emoji)
                    label = f"{emoji} {count}" if count > 0 else emoji
                    if st.button(label, key=f"react_{expense_id}_{emoji}", use_container_width=True):
                        from database import add_reaction
                        add_reaction(expense_id, username, emoji)
                        st.cache_data.clear()
                        st.rerun()

    # Load more
    if offset + PAGE_SIZE < len(sorted_rows):
        if st.button("Load more..."):
            st.session_state["feed_offset"] = offset + PAGE_SIZE
            st.rerun()
    else:
        st.caption("You've seen everything! 💕")
```

- [ ] **Step 3: Smoke test the feed page**

```
streamlit run app.py
```

- Navigate to `?page=feed`
- Expenses should appear as cards grouped Today/Yesterday/Past
- Reaction buttons should appear below each card
- Clicking a reaction button should toggle it (add/remove) and rerun

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(feed): implement feed page with expense cards and emoji reactions"
```

---

### Task 5: Add profile mini-cards to dashboard

**Files:**
- Modify: `app.py` (`page_dashboard`)

- [ ] **Step 1: Find `page_dashboard` in `app.py`**

Look for `def page_dashboard(` — this is the main home page function.

- [ ] **Step 2: At the very top of the dashboard content (after the date range setup, before existing st.subheader calls), insert the profile mini-cards block**

```python
# --- Partner Profile Mini-Cards ---
all_rows_dash = _cached_all_expenses()
from datetime import date as _dt
_this_month = _dt.today().replace(day=1)
_today_dt = _dt.today()
month_rows_all = [
    r for r in all_rows_dash
    if str(r.get("date", ""))[:7] == _this_month.strftime("%Y-%m")
]
streaks_dash = get_streaks(all_rows_dash)

def _profile_stats(user: str) -> dict:
    user_rows = [r for r in month_rows_all if r.get("added_by") == user]
    total = sum(r.get("amount", 0) for r in user_rows)
    streak_key = "jude_streak" if user == "husband" else "wincyl_streak"
    streak = streaks_dash.get(streak_key, 0)
    lp = love_points(rows_to_dataframe(user_rows))
    # Top category
    cat_totals: dict = {}
    for r in user_rows:
        cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r.get("amount", 0)
    top_cat = max(cat_totals, key=cat_totals.get) if cat_totals else ""
    CAT_EMOJI = {"Housing":"🏠","Food":"🍔","Health":"💊","Transportation":"🚗","Personal":"💅","Entertainment":"🎬","Others":"📦"}
    top_cat_str = f"{CAT_EMOJI.get(top_cat, '')} {top_cat} fan" if top_cat else ""
    return {"total": total, "streak": streak, "tier_emoji": lp["emoji"], "tier_label": lp["label"], "top_category": top_cat_str}

pc1, pc2 = st.columns(2)
with pc1:
    st.markdown(styles.card_profile("husband", _profile_stats("husband")), unsafe_allow_html=True)
with pc2:
    st.markdown(styles.card_profile("wife", _profile_stats("wife")), unsafe_allow_html=True)

st.divider()
```

- [ ] **Step 3: Smoke test the dashboard**

```
streamlit run app.py
```

- Navigate to home (`?page=home`)
- Two profile cards should appear side by side at the top
- Each should show name, this-month total, streak, and love tier

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(dashboard): add partner profile mini-cards at top of home page"
```

---

## Chunk 4: Quick Add Dialog + Mobile Polish

**Files:**
- Modify: `app.py` (add `@st.dialog` quick-add, wire FAB)

---

### Task 6: Quick-add dialog via FAB

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Find `page_add_expense()` in `app.py`**

This is the existing add expense form page.

- [ ] **Step 2: Add a `@st.dialog` decorated function above `page_add_expense`**

```python
@st.dialog("➕ Quick Add")
def quick_add_dialog(username: str):
    """Streamlit dialog for quick expense entry from FAB."""
    amount = st.number_input("Amount ($)", min_value=0.01, max_value=float(MAX_AMOUNT), step=1.0, format="%.2f")
    category = st.selectbox("Category", CATEGORIES)
    description = st.text_input("Description (optional)", max_chars=MAX_DESCRIPTION_LENGTH)
    exp_date = st.date_input("Date", value=date.today())

    if st.button("Add Expense 💕", use_container_width=True, type="primary"):
        err = validate_expense(amount, category, description)
        if err:
            st.error(err)
        else:
            add_expense(float(amount), category, description, str(exp_date), username)
            st.cache_data.clear()
            st.success("Added! 🎉")
            st.rerun()
```

- [ ] **Step 3: Update the routing in `main()` so navigating to `?page=add` opens the dialog on the home page**

In the `main()` routing block, change the `"add"` entry so it opens the dialog instead of navigating to a full page:

```python
# In main(), before PAGE_MAP lookup:
if page_key == "add":
    page_key = "home"  # render home page behind the dialog
    if not st.session_state.get("add_dialog_opened"):
        st.session_state["add_dialog_opened"] = True
        quick_add_dialog(username)
    else:
        # Dialog closed (rerun after submit/dismiss) — clear flag and return to home
        del st.session_state["add_dialog_opened"]
        st.query_params["page"] = "home"
        st.rerun()

# Then render the page as normal
PAGE_MAP[page_key](username)
```

> `add_dialog_opened` is explicitly cleared after the dialog closes so the FAB can be clicked again.

- [ ] **Step 4: Smoke test the FAB flow**

```
streamlit run app.py
```

- Click the ➕ button in the bottom nav
- Dialog should slide up from the bottom (on mobile) or appear as a modal (on desktop)
- Fill in amount + category and click Add — should succeed and return to home

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(add): quick-add dialog via FAB using @st.dialog"
```

---

## Chunk 5: Easter Eggs

**Files:**
- Modify: `app.py` (check and trigger easter eggs in relevant page functions)
- Modify: `database.py` (import `get_easter_egg`, `set_easter_egg` — already added in Chunk 1)

---

### Task 7: Implement the 6 server-side easter eggs

*Note: The long-press card flip (Easter egg 7) is pure CSS/JS in `card_expense()` and is already included in `styles.py`. No additional server-side work needed for it.*

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add `get_easter_egg` and `set_easter_egg` to the `database` import in `app.py`**

- [ ] **Step 2: Add fortune cookie trigger in `page_add_expense()`**

After a successful `add_expense()` call in `page_add_expense()`, add:

```python
import random as _random
if _random.random() < 0.05:
    fortune = _random.choice(styles.FORTUNE_MESSAGES)
    st.markdown(styles.easter_egg_fortune(fortune), unsafe_allow_html=True)
```

- [ ] **Step 2b: Add the same fortune cookie trigger inside `quick_add_dialog()`**

After the successful `add_expense()` call in `quick_add_dialog()`, add:

```python
import random as _random
if _random.random() < 0.05:  # 1-in-20 chance
    fortune = _random.choice(styles.FORTUNE_MESSAGES)
    st.markdown(styles.easter_egg_fortune(fortune), unsafe_allow_html=True)
```

- [ ] **Step 3: Add Sync'd banner check in `page_dashboard()`**

At the top of dashboard, after loading `all_rows_dash`, add:

```python
# Easter egg: Sync'd — both partners logged today
_today_str = str(date.today())
_jude_today = any(
    str(r.get("date",""))[:10] == _today_str and r.get("added_by") == "husband"
    for r in all_rows_dash
)
_wincyl_today = any(
    str(r.get("date",""))[:10] == _today_str and r.get("added_by") == "wife"
    for r in all_rows_dash
)
_last_sync = get_easter_egg("last_sync_date", "")
if _jude_today and _wincyl_today and _last_sync != _today_str:
    set_easter_egg("last_sync_date", _today_str)
    st.markdown(styles.sync_banner(), unsafe_allow_html=True)
```

- [ ] **Step 4: Add achievement unlock confetti in `page_rewards()` (or `page_dashboard()`)**

In the rewards page, after computing `achievements`, add:

```python
import json as _json
_seen_raw = get_easter_egg("seen_achievements", "[]")
try:
    _seen = set(_json.loads(_seen_raw))
except Exception:
    _seen = set()
_now_unlocked = {a["name"] for a in achievements if a["unlocked"]}
_newly_unlocked = _now_unlocked - _seen
if _newly_unlocked:
    set_easter_egg("seen_achievements", _json.dumps(list(_now_unlocked)))
    st.markdown(styles.confetti_burst(), unsafe_allow_html=True)
    for name in _newly_unlocked:
        st.toast(f"🏆 Achievement unlocked: {name}!", icon="🎊")
```

- [ ] **Step 5: Add Silent Saver mystery badge check in `page_rewards()`**

After loading `all_rows_for_streaks`, add:

```python
# Easter egg: Silent Saver — spend < $50 in any completed month with no hint
if get_easter_egg("silent_saver_unlocked", "0") == "0":
    from collections import defaultdict as _dd
    _month_totals: dict = _dd(float)
    for _r in all_rows_for_streaks:
        _ym = str(_r.get("date",""))[:7]
        _month_totals[_ym] += _r.get("amount", 0)
    _today_ym = date.today().strftime("%Y-%m")
    _silent_months = [m for m, t in _month_totals.items() if t < 50 and m < _today_ym]
    if _silent_months:
        set_easter_egg("silent_saver_unlocked", "1")
        st.markdown(styles.confetti_burst(), unsafe_allow_html=True)
        st.info("🤫 **The Silent Saver** — A mystery badge has been unlocked. Some secrets reveal themselves to those who spend wisely.")
```

- [ ] **Step 6: Add app anniversary check in `page_dashboard()`**

After loading `all_rows_dash`, add:

```python
# Easter egg: App anniversary
if all_rows_dash:
    _first_date_str = min(str(r.get("date",""))[:10] for r in all_rows_dash)
    try:
        _first_date = date.fromisoformat(_first_date_str)
        _today_d = date.today()
        if _first_date.month == _today_d.month and _first_date.day == _today_d.day and _first_date.year < _today_d.year:
            _years = _today_d.year - _first_date.year
            _anniv_key = f"anniv_{_today_d.year}"
            if get_easter_egg(_anniv_key, "0") == "0":
                set_easter_egg(_anniv_key, "1")
                st.markdown(styles.confetti_burst(), unsafe_allow_html=True)
                st.balloons()
                st.success(f"🎂 {_years} year{'s' if _years > 1 else ''} of tracking love together! Happy FamilyLedger Anniversary! 💕")
    except Exception:
        pass
```

- [ ] **Step 7: Add couple stats hidden panel HTML to `page_dashboard()`**

The logo-tap easter egg (5 taps → show panel) requires the panel HTML to exist in the DOM. Add this at the end of the dashboard page (hidden by default):

```python
# Hidden couple stats panel (revealed by 5 logo taps via JS in app_header)
if all_rows_dash:
    _all_df = rows_to_dataframe(all_rows_dash)
    _max_day = _all_df.groupby(_all_df["date"].dt.date)["amount"].sum().idxmax() if not _all_df.empty else "N/A"
    _max_day_total = _all_df.groupby(_all_df["date"].dt.date)["amount"].sum().max() if not _all_df.empty else 0
    _total_logged = len(all_rows_dash)
    _top_cat = _all_df.groupby("category")["amount"].sum().idxmax() if not _all_df.empty else "N/A"
    _max_expense = _all_df["amount"].max() if not _all_df.empty else 0
    st.markdown(f"""
<div id="couple-stats-panel" style="display:none;background:#1a1a2e;border:2px solid #c44dff;
border-radius:14px;padding:20px;margin:12px 0">
  <div style="color:#c44dff;font-weight:bold;margin-bottom:12px">🔮 Secret Couple Stats</div>
  <div style="color:#e0e0e0;font-size:0.85em;line-height:2">
    💸 Most expensive day: <strong>{_max_day}</strong> (${_max_day_total:,.2f})<br>
    💕 Total expenses logged together: <strong>{_total_logged}</strong><br>
    📦 Most used category: <strong>{_top_cat}</strong><br>
    💎 Highest single expense: <strong>${_max_expense:,.2f}</strong>
  </div>
</div>
""", unsafe_allow_html=True)
```

- [ ] **Step 8: Smoke test all easter eggs**

```
streamlit run app.py
```

- Add an expense 20 times — fortune cookie should appear ~once
- Check rewards page — if any achievement just unlocked, confetti should fire
- Tap the 💕 logo header 5 times — couple stats panel should appear

- [ ] **Step 9: Commit**

```bash
git add app.py database.py
git commit -m "feat(easter-eggs): add fortune cookie, sync banner, confetti, silent saver, anniversary, couple stats"
```

---

## Chunk 6: Final Polish + Existing Page Migration

**Files:**
- Modify: `app.py` (update `page_rewards`, `page_analysis`, `page_budgets`, `page_search`, `page_monthly_view` to use card HTML where applicable)

---

### Task 8: Update rewards page to use card layout

- [ ] **Step 1: Verify `achievements` dict has `unlocked_date` key**

In `analysis.py`, `get_achievements()` returns dicts with `"unlocked_date"` (a date string or `None`). Confirm by checking the `_empty` list — each entry has `"unlocked_date": None`. The code below uses `ach.get("unlocked_date")` which safely handles `None`. No change to `analysis.py` needed.

- [ ] **Step 2: In `page_rewards()`, replace the achievement grid with card HTML**

Find the existing `ach_cols = st.columns(...)` loop and replace with:

```python
st.markdown('<div style="display:flex;flex-wrap:wrap;gap:10px;">', unsafe_allow_html=True)
for ach in achievements:
    opacity = "1" if ach["unlocked"] else "0.35"
    border = "#c44dff" if ach["unlocked"] else "#333"
    date_str = f"<div style='color:#888;font-size:0.65em'>Unlocked: {ach['unlocked_date']}</div>" if ach.get("unlocked_date") else ""
    st.markdown(f"""
<div style="background:#1a1a2e;border-radius:12px;padding:14px;
border:1px solid {border};opacity:{opacity};text-align:center;
min-width:140px;flex:1">
  <div style="font-size:2em">{ach['emoji']}</div>
  <div style="font-weight:bold;color:#e0e0e0;font-size:0.85em">{ach['name']}</div>
  <div style="color:#999;font-size:0.72em;margin-top:4px">{ach['description']}</div>
  {date_str}
</div>""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: Final smoke test — navigate through all pages**

```
streamlit run app.py
```

Check: Home, Feed, Rewards, Analysis, More → Budgets, More → Search. Verify:
- No sidebar visible
- Bottom nav present on all pages
- Header present on all pages
- Cards render correctly
- No Python errors in terminal

- [ ] **Step 3: Final commit**

```bash
git add app.py
git commit -m "feat(ui): update rewards page to card layout, complete social UI redesign"
```
