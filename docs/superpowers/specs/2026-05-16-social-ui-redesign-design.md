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

### Implementation
Streamlit does not natively support a bottom nav bar. We inject a fixed-position HTML nav bar via `st.markdown(unsafe_allow_html=True)` and use `st.query_params` to track active page, replacing the current sidebar radio.

---

## 4. Feed & Card Design

### Expense Cards (Facebook Post Style)
Each expense renders as a card with:
- **Header:** Avatar circle (J/W) + display name + "X hours/days ago"
- **Body:** Category emoji + amount (bold headline) + description
- **Footer:** Emoji reaction bar — 💕 ❤️ 😂 😮 — clickable, stored in `reactions` table
- **Badge:** 🔄 for recurring expenses

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
- FAB ➕ button (raised, gradient, center of bottom nav) opens a slide-up panel
- Fields: Amount (large input, numeric keyboard), Category (big tap targets), Description (optional, collapsed)
- Date defaults to today
- Submit button full-width at bottom of sheet
- Dismissable by tapping outside or swiping down

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

Easter egg state tracked in `easter_egg_state` DB table. Fortune cookie messages and couple stats copy live in `styles.py`.

---

## 7. styles.py — Component Library

Centralizes all HTML/CSS templates currently scattered across `app.py`:

```python
def card_expense(row, reactions) -> str: ...
def card_profile(user, stats) -> str: ...
def bottom_nav(active_page) -> str: ...
def app_header(username) -> str: ...
def bottom_sheet_add() -> str: ...
def confetti_burst() -> str: ...
def easter_egg_fortune(message) -> str: ...
def sync_banner() -> str: ...
```

Each function returns an HTML string injected via `st.markdown(unsafe_allow_html=True)`.

---

## 8. Out of Scope

- Push notifications (requires a server process outside Streamlit)
- Real-time sync between partners (Streamlit reruns on interaction only)
- Dark/light mode toggle (stays dark — matches the couple's current preference)
- New expense categories (fixed list unchanged)
