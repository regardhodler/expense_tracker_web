# Social UI Redesign & Reward System Fix — Design Spec

**Date:** 2026-05-16  
**Status:** Approved  
**Scope:** Bug fix (MoM love points), Facebook-style UI overhaul, mobile-first redesign, easter eggs

---

## 1. Bug Fix — Month-over-Month Love Points

### Problem
`page_analysis` computes `_down_months` by comparing all consecutive months in the selected year, including the current in-progress month. A partial May (16 days of spending) compared against a complete April (30 days) will almost always appear cheaper, falsely awarding love points.

### Fix
Cap the MoM comparison to **completed months only** — i.e., months where `month_index < current_month`. One-line change in `page_analysis`:

```python
# Before
_mom_vals = [_monthly.get(m, 0) for m in range(1, 13)]
_down_months = sum(
    1 for i in range(1, 12)
    if _mom_vals[i] > 0 and _mom_vals[i - 1] > 0 and _mom_vals[i] < _mom_vals[i - 1]
)

# After — only compare completed months (before current month)
_today = date.today()
_completed_months = _today.month  # e.g. May = 5, so months 1–4 are complete
_mom_vals = [_monthly.get(m, 0) for m in range(1, 13)]
_down_months = sum(
    1 for i in range(1, _completed_months)  # stop before current month
    if _mom_vals[i] > 0 and _mom_vals[i - 1] > 0 and _mom_vals[i] < _mom_vals[i - 1]
)
```

Also fix `_yr_end` for the current year to cap at today instead of Dec 31 (prevents querying future months):
```python
_yr_end = min(date(_year_sel, 12, 31), date.today()) if _year_sel == _today.year else date(_year_sel, 12, 31)
```

---

## 2. Architecture

### Files Changed

| File | Change |
|------|--------|
| `analysis.py` | Bug fix only (one line) |
| `database.py` | Add `reactions` table and `easter_egg_state` table |
| `app.py` | Full page layout rewrite; new Feed page; bottom nav |
| `visualization.py` | Minor mobile chart sizing tweaks |
| `styles.py` | **New file** — centralized CSS/HTML component library |

### New DB Tables

**`reactions`**
```sql
CREATE TABLE reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL,
    reacted_by TEXT NOT NULL,       -- 'husband' or 'wife'
    emoji TEXT NOT NULL,            -- '💕', '❤️', '😂', '😮'
    created_at TEXT NOT NULL
);
```

**`easter_egg_state`**
```sql
CREATE TABLE easter_egg_state (
    key TEXT PRIMARY KEY,           -- e.g. 'logo_taps', 'silent_saver_unlocked'
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### No new dependencies
Everything stays within Streamlit + SQLite. No React, no build pipeline.

---

## 3. Navigation — Hybrid Header + Bottom Nav

### Layout
- **Top:** Branded header — "💕 FamilyLedger" on the left, notification bell + user avatar initial on the right
- **Bottom (mobile):** Fixed tab bar with 5 slots
- **Desktop:** Sidebar replaced by a thin icon-only rail

### Bottom Tab Bar

| Position | Label | Icon | Page |
|----------|-------|------|------|
| 1 | Home | 🏠 | Dashboard + Feed |
| 2 | Feed | 📰 | Full expense feed |
| 3 | **Add** | ➕ | Quick-add bottom sheet (raised FAB) |
| 4 | Rewards | 🏆 | Streaks + Achievements + Love |
| 5 | More | ☰ | Budgets, Search, Monthly View, Settings |

### Implementation — Routing Mechanism
Streamlit does not natively support a bottom nav bar. The bridge works as follows:

1. Each nav tab renders as an `<a href="?page=home">` anchor tag inside a fixed-position HTML block injected via `st.markdown(unsafe_allow_html=True)`.
2. Clicking a tab triggers a full browser navigation to `?page=<name>`, which Streamlit treats as a rerun with updated query params.
3. `app.py` reads `st.query_params.get("page", "home")` at startup to determine which page function to call — replacing the current sidebar radio. Any unknown `?page=` value defaults to `"home"`.
4. The active tab is highlighted by comparing `st.query_params["page"]` to each tab's `data-page` value and injecting a selected CSS class in `bottom_nav()`.
5. The sidebar (`st.sidebar`) is hidden globally via CSS: `section[data-testid="stSidebar"] { display: none !important; }` injected in the app header.

**Edge case:** The ➕ FAB does not navigate — it sets `st.session_state["show_add_sheet"] = True` via a hidden Streamlit button triggered by JS (`document.getElementById("fab-trigger").click()`), then the page reruns and renders the bottom sheet.

---

## 4. Feed & Card Design

### Expense Cards (Facebook Post Style)
Each expense renders as a card with:
- **Header:** Avatar circle (J/W) + display name + "X hours/days ago"
- **Body:** Category emoji + amount (bold headline) + description
- **Footer:** Emoji reaction bar — 💕 ❤️ 😂 😮 — clickable, stored in `reactions` table
- **Badge:** 🔄 for recurring expenses

### Reaction Write Path
Streamlit HTML cannot handle clicks natively. Reactions use a **hidden Streamlit button bridge**:
1. Each card renders 4 emoji buttons as `<button onclick="reactTo(expense_id, emoji)">`.
2. `reactTo()` sets a hidden `<input id="react-payload">` value to `"expense_id:emoji"`, then calls `document.getElementById("react-trigger").click()`.
3. `react-trigger` is a hidden `st.button` rendered off-screen. Its click triggers a Streamlit rerun.
4. On rerun, `app.py` reads `st.session_state.get("react_payload")` (synced from the input via a JS→session bridge using `st.components.v1.html` postMessage), calls `add_reaction(expense_id, emoji, username)` in `database.py`, and clears the payload.
5. The reaction count updates optimistically in HTML before the rerun via JS counter increment.

**Fallback decision:** Ship the `st.button` row fallback as the **primary implementation** (simpler, zero JS, no postMessage risk). If it looks visually acceptable, skip the full JS bridge entirely. Only invest in the bridge if the button-row layout feels too clunky after seeing it live.

### Feed Page
- Grouped: Today / Yesterday / Past (same as current Recent section)
- Full-width cards, touch-friendly tap targets
- Infinite scroll (Streamlit pagination via `st.session_state` offset)

### Home Page Profile Mini-Cards
Two cards side-by-side at top of dashboard (stack vertically on mobile):
- Avatar + name
- This month's total
- Current streak 🔥
- Love tier emoji + label
- Spending personality tag (derived from top category this month)

---

## 5. Mobile UX Improvements

### Quick Add — Bottom Sheet
The FAB ➕ button uses Streamlit's `@st.dialog` decorator (available since Streamlit 1.31) as the bottom sheet:

```python
@st.dialog("➕ Add Expense")
def quick_add_dialog():
    amount = st.number_input("Amount", min_value=0.01, ...)
    category = st.selectbox("Category", CATEGORIES)
    description = st.text_input("Description (optional)")
    if st.button("Add", use_container_width=True):
        add_expense(...)
        st.rerun()
```

The FAB button in the bottom nav HTML calls a hidden `st.button` via JS (same bridge as reactions). When `st.session_state["show_add_sheet"]` is True, `quick_add_dialog()` is called and the modal opens. CSS overrides the default dialog to slide up from bottom on mobile. Target the Streamlit 1.31+ dialog testid (known fragility — may need updating if Streamlit changes internal class names):
```css
div[data-testid="stDialog"] > div {
  position: fixed; bottom: 0; left: 0; right: 0; top: auto;
  border-radius: 16px 16px 0 0; max-height: 80vh;
}
```
If this selector breaks after a Streamlit upgrade, fall back to a full-page `st.form` on the Add page instead. Dismiss by clicking outside (Streamlit dialog default behavior) or submitting the form.

### Dashboard on Mobile
- Profile cards stack vertically
- Stat chips (total spent, streak, love tier) shown as large bold numbers before charts
- All charts full-width, no horizontal scroll
- Recent expenses as cards, not table rows

### Responsive Breakpoints
- Mobile: `max-width: 768px` — bottom nav, stacked cards, bottom sheet
- Desktop: sidebar rail (icons only), side-by-side cards, modal dialog for add

---

## 6. Easter Eggs

| Trigger | Effect | Type |
|---------|--------|------|
| Tap 💕 logo 5 times | Hidden "Couple Stats" panel slides in (all-time records, funny superlatives) | Hidden lore |
| Both partners log on same day | "Sync'd! ✨" surprise banner on next dashboard load | Silly surprise |
| New achievement unlocks | Confetti explosion (CSS animation) fills screen for 2 seconds | Milestone celebration |
| 1-in-20 chance on expense submit | Random "fortune cookie" message appears in a toast | Silly surprise |
| Spend < $50 in any month (no hint) | "The Silent Saver 🤫" mystery badge unlocks with cryptic reveal message | Hidden lore |
| App anniversary date (first expense date) | Full-screen celebration animation + "X years of tracking love 💕" | Milestone celebration |
| Long-press (3s) any expense card | Card flips to show "fun fact" about that spending category | Hidden lore |

### Easter Egg State Machine

Each easter egg has a **trigger**, a **check location** (where in the code it's evaluated), and a **DB key** for persistence:

| Easter Egg | DB Key | Trigger Check Location | State Values |
|------------|--------|----------------------|--------------|
| Logo taps | `logo_tap_count` | JS counter in `app_header()`, resets after 5 | `"0"`–`"5"` |
| Sync'd day | `last_sync_date` | `page_dashboard()` on load, compare both partners' last log dates | `"YYYY-MM-DD"` or `""` |
| Achievement unlock | `seen_achievements` | `page_rewards()` diff between previous and current unlocked list | JSON list of seen names |
| Fortune cookie | n/a (stateless) | `page_add_expense()` after successful submit, `random.random() < 0.05` | — |
| Silent Saver | `silent_saver_unlocked` | `page_rewards()` on load, check prior completed months < $50 total | `"0"` or `"1"` |
| Anniversary | `app_start_date` | `page_dashboard()` on load, compare today to first expense date anniversary | `"YYYY-MM-DD"` |
| Long-press card | n/a (stateless) | CSS/JS `touchstart`/`touchend` timer in card HTML, 3s threshold | — |

**Logo tap implementation:** The header HTML includes a JS counter in `sessionStorage`. After 5 taps, JS sets `st.session_state` via the hidden-button bridge and calls `db.upsert_easter_egg("logo_tap_count", "0")` to reset.

**Jan 1 edge case (bug fix):** If `_today.month == 1`, `_completed_months = 1` means `range(1, 1)` is empty → `_down_months = 0`. Correct behavior — no completed month-pairs to compare yet.

---

## 7. styles.py — Component Library

Centralizes all HTML/CSS templates currently scattered across `app.py`:

```python
def card_expense(row: dict, reactions: list[dict], current_user: str) -> str:
    """Returns HTML for one expense card. row = DB row dict. reactions = list of reaction dicts for this expense_id. current_user = 'husband'|'wife'."""

def card_profile(user: str, stats: dict) -> str:
    """Returns HTML for one partner profile mini-card. stats = {total, streak, tier_emoji, tier_label, top_category}."""

def bottom_nav(active_page: str) -> str:
    """Returns fixed-position bottom nav HTML. active_page = one of: 'home','feed','add','rewards','more'."""

def app_header(username: str, notif_count: int = 0) -> str:
    """Returns branded top header HTML. notif_count drives the bell badge."""

def global_css() -> str:
    """Returns <style> block: sidebar hide, responsive breakpoints, card styles, bottom nav spacing."""

def confetti_burst() -> str:
    """Returns self-contained HTML+CSS+JS confetti animation. Auto-destroys after 2.5s."""

def easter_egg_fortune(message: str) -> str:
    """Returns toast-style HTML for fortune cookie message. message = one of FORTUNE_MESSAGES list."""

def sync_banner() -> str:
    """Returns 'Sync'd! ✨' surprise banner HTML. Called once per day when both partners logged."""
```

**Constants in `styles.py`** (hardcoded, not DB-driven):
```python
FORTUNE_MESSAGES: list[str]
# 20 strings, e.g.:
# "A couple that budgets together, stays together 💕"
# "Your wallet thanks you. Your heart thanks you more. 🌹"
# "Frugality is just romance with a spreadsheet. 📊"
# ... (engineer writes remaining 17 in same tone)

CATEGORY_FUN_FACTS: dict[str, str]
# One fun fact per category, e.g.:
# "Food": "The average Canadian spends $1,050/month on food. You're feeding love! 🍔"
# "Housing": "Your home is your castle — and your biggest budget item. 🏰"
# ... (one per CATEGORIES list)

COUPLE_STATS_LABELS: list[str]
# Labels for the hidden couple stats panel, e.g.:
# "Most expensive single day ever 💸"
# "Biggest food month 🍔"
# "Longest streak 🔥"
# "Total logged together 💕"
# "Most used category 📦"
```
Content is intentionally light/playful in tone. Engineer writes the copy; no external content source needed.

Each function returns an HTML string injected via `st.markdown(unsafe_allow_html=True)`.

---

## 8. Out of Scope

- Push notifications (requires a server process outside Streamlit)
- Real-time sync between partners (Streamlit reruns on interaction only)
- Dark/light mode toggle (stays dark — matches the couple's current preference)
- New expense categories (fixed list unchanged)
