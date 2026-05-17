"""HTML/CSS component library for the expense tracker social UI."""

from __future__ import annotations

import html
import random
from datetime import date as _date

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

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------


def global_css() -> str:
    """CSS injected once at app startup."""
    return """
<style>
section[data-testid="stSidebar"] { display: none !important; }

@media (max-width: 768px) {
    .main .block-container { padding-bottom: 80px !important; }
}

.exp-card {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    border: 1px solid #2a2a4a;
}
.exp-card:hover { border-color: #c44dff44; }

.avatar {
    width: 52px; height: 36px;
    border-radius: 18px;
    background: linear-gradient(135deg, #ff6b9d, #c44dff);
    display: flex; align-items: center; justify-content: center;
    font-weight: bold; color: #fff; font-size: 0.72em;
    flex-shrink: 0;
    padding: 0 6px;
    white-space: nowrap;
}

.profile-card {
    background: #1a1a2e;
    border-radius: 14px;
    padding: 16px;
    border: 1px solid #2a2a4a;
    text-align: center;
}

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
    height: 30px; border-radius: 15px;
    background: linear-gradient(135deg, #ff6b9d, #c44dff);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.72em; font-weight: bold; color: #fff;
    padding: 0 10px; white-space: nowrap;
}

@media (max-width: 768px) {
    div[data-testid="stDialog"] > div {
        position: fixed !important; bottom: 0 !important; left: 0 !important;
        right: 0 !important; top: auto !important;
        border-radius: 16px 16px 0 0 !important;
        max-height: 85vh !important;
    }
}

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


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


def app_header(username: str, notif_count: int = 0) -> str:
    """Branded top header. username = 'husband' | 'wife'."""
    initial = "Jude" if username == "husband" else "Wincyl"
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
        var p = document.getElementById('couple-stats-panel');
        if (p) p.style.display = 'block';
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
    """Single expense card HTML."""
    _DISPLAY = {"husband": "Jude", "wife": "Wincyl"}
    added_by = row.get("added_by", "")
    initial = "Jude" if added_by == "husband" else "Wincyl"
    display_name = html.escape(_DISPLAY.get(added_by, added_by))
    desc = row.get("description", "") or ""
    is_recurring = desc.startswith("[Recurring]")
    badge = '<span style="font-size:0.7em;background:#2a2a4a;padding:2px 6px;border-radius:8px">🔄 Recurring</span>' if is_recurring else ""
    clean_desc = desc.replace("[Recurring] ", "") if is_recurring else desc
    clean_desc = html.escape(clean_desc)

    CATEGORY_EMOJI = {
        "Housing": "🏠", "Food": "🍔", "Health": "💊",
        "Transportation": "🚗", "Personal": "💅",
        "Entertainment": "🎬", "Others": "📦",
    }
    cat = html.escape(row.get("category", "Others"))
    cat_emoji = CATEGORY_EMOJI.get(row.get("category", "Others"), "📦")

    raw_date = str(row.get("date", ""))[:10]
    try:
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
    amount = row.get("amount", 0)
    return f"""
<div class="exp-card" data-expense-id="{expense_id}">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
    <div class="avatar">{initial}</div>
    <div>
      {f'<div style="font-size:0.75em">{badge}</div>' if badge else ''}
      <div style="color:#666;font-size:0.72em">{time_str}</div>
    </div>
  </div>
  <div style="font-size:1.15em;font-weight:bold;color:#ff6b9d">{cat_emoji} ${amount:,.2f} <span style="color:#888;font-weight:normal;font-size:0.8em">{cat}</span></div>
  {f'<div style="color:#aaa;font-size:0.82em;margin-top:4px">{clean_desc}</div>' if clean_desc else ''}
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px">{reaction_html}</div>
</div>
"""


def card_profile(user: str, stats: dict) -> str:
    """Partner profile mini-card."""
    _DISPLAY = {"husband": "Jude", "wife": "Wincyl"}
    initial = "Jude" if user == "husband" else "Wincyl"
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
  <div style="color:#888;font-size:0.75em">{tier_emoji} {tier_label}</div>
  {f'<div style="color:#666;font-size:0.72em;margin-top:4px">🔥 {streak} day streak</div>' if streak > 0 else ''}
  {f'<div style="color:#666;font-size:0.72em">{top_cat}</div>' if top_cat else ''}
</div>
"""


def confetti_burst() -> str:
    """Self-contained confetti animation. Auto-removes after 3.5s."""
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
    """Sync'd banner shown when both partners logged today."""
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
@keyframes sync-pop {
    from { transform: scale(0.85); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
}
</style>
"""
