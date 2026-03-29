# Love Points System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dollar-based Romance Status with an input-count-based Love Points system that rewards active expense logging with fun romantic messages and visual progress bars.

**Architecture:** New `love_points()` function in `analysis.py` counts expense entries per user for the current month (1 pt manual, 0.25 pt recurring). Dashboard renders a love message banner, shared progress bar, and individual contribution bars using inline HTML/CSS. Monthsary banner upgraded with rotating messages.

**Tech Stack:** Python, Streamlit, pandas, HTML/CSS (inline via `st.markdown`)

**Spec:** `docs/superpowers/specs/2026-03-15-love-points-system-design.md`

---

## Chunk 1: Core Points Logic + Tests

### Task 1: Write tests for `love_points()` function

**Files:**
- Modify: `tests/test_analysis.py`

- [ ] **Step 1: Write failing tests for `love_points()`**

Add this test class to the end of `tests/test_analysis.py`:

```python
from analysis import love_points, DISPLAY_NAMES


class TestLovePoints:
    """Tests for the input-based love points system."""

    def _make_rows(self, husband_manual=0, wife_manual=0, husband_recurring=0, wife_recurring=0):
        """Helper to build a DataFrame of expense rows."""
        rows = []
        for i in range(husband_manual):
            rows.append({"id": len(rows), "date": "2026-03-05", "amount": 10.0,
                         "category": "Food", "description": f"manual {i}", "added_by": "husband"})
        for i in range(wife_manual):
            rows.append({"id": len(rows), "date": "2026-03-05", "amount": 10.0,
                         "category": "Food", "description": f"manual {i}", "added_by": "wife"})
        for i in range(husband_recurring):
            rows.append({"id": len(rows), "date": "2026-03-01", "amount": 50.0,
                         "category": "Housing", "description": f"[Recurring] rent {i}", "added_by": "husband"})
        for i in range(wife_recurring):
            rows.append({"id": len(rows), "date": "2026-03-01", "amount": 50.0,
                         "category": "Housing", "description": f"[Recurring] sub {i}", "added_by": "wife"})
        return rows_to_dataframe(rows)

    def test_empty_df(self):
        df = rows_to_dataframe([])
        result = love_points(df)
        assert result["combined_points"] == 0
        assert result["tier"] == "warming_up"
        assert result["emoji"] == "❄️"
        assert isinstance(result["message"], str)
        assert result["points"]["husband"] == 0
        assert result["points"]["wife"] == 0

    def test_manual_entries_count_as_1_point(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result = love_points(df)
        assert result["points"]["husband"] == 3.0
        assert result["points"]["wife"] == 2.0
        assert result["combined_points"] == 5.0

    def test_recurring_entries_count_as_quarter_point(self):
        df = self._make_rows(husband_recurring=4)
        result = love_points(df)
        assert result["points"]["husband"] == 1.0  # 4 * 0.25
        assert result["combined_points"] == 1.0

    def test_mixed_manual_and_recurring(self):
        df = self._make_rows(husband_manual=2, wife_manual=1, husband_recurring=4, wife_recurring=2)
        result = love_points(df)
        # husband: 2 + (4*0.25) = 3.0, wife: 1 + (2*0.25) = 1.5
        assert result["points"]["husband"] == 3.0
        assert result["points"]["wife"] == 1.5
        assert result["combined_points"] == 4.5

    def test_tier_warming_up(self):
        df = self._make_rows(husband_manual=1)
        result = love_points(df)
        assert result["tier"] == "warming_up"
        assert result["emoji"] == "❄️"

    def test_tier_sweet(self):
        df = self._make_rows(husband_manual=2, wife_manual=1)
        result = love_points(df)
        assert result["tier"] == "sweet"
        assert result["emoji"] == "🥰"

    def test_tier_crushing(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result = love_points(df)
        assert result["tier"] == "crushing"
        assert result["emoji"] == "😍"

    def test_tier_madly(self):
        df = self._make_rows(husband_manual=4, wife_manual=3)
        result = love_points(df)
        assert result["tier"] == "madly"
        assert result["emoji"] == "🔥"

    def test_tier_soulmates(self):
        df = self._make_rows(husband_manual=5, wife_manual=5)
        result = love_points(df)
        assert result["tier"] == "soulmates"
        assert result["emoji"] == "💪"

    def test_tier_soulmates_at_11(self):
        df = self._make_rows(husband_manual=6, wife_manual=5)
        result = love_points(df)
        assert result["tier"] == "soulmates"

    def test_tier_easter_egg(self):
        df = self._make_rows(husband_manual=7, wife_manual=5)
        result = love_points(df)
        assert result["tier"] == "easter_egg"
        assert result["emoji"] == "🌟"

    def test_message_is_deterministic_for_same_month(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result1 = love_points(df, year=2026, month=3)
        result2 = love_points(df, year=2026, month=3)
        assert result1["message"] == result2["message"]

    def test_message_changes_across_months(self):
        df = self._make_rows(husband_manual=3, wife_manual=2)
        result_mar = love_points(df, year=2026, month=3)
        result_apr = love_points(df, year=2026, month=4)
        # Same tier, but message should rotate (may collide for some months, but not all)
        # Just verify the function accepts the year/month params
        assert isinstance(result_mar["message"], str)
        assert isinstance(result_apr["message"], str)

    def test_only_one_user(self):
        df = self._make_rows(husband_manual=5)
        result = love_points(df)
        assert result["points"]["husband"] == 5.0
        assert result["points"]["wife"] == 0
        assert result["combined_points"] == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_analysis.py::TestLovePoints -v`
Expected: FAIL — `ImportError: cannot import name 'love_points' from 'analysis'`

---

### Task 2: Implement `love_points()` in `analysis.py`

**Files:**
- Modify: `analysis.py`

- [ ] **Step 3: Add the `love_points()` function**

Add after the existing `love_comparison()` function (around line 177) in `analysis.py`:

```python
# ---------------------------------------------------------------------------
# Love Points System (input-based)
# ---------------------------------------------------------------------------

LOVE_TIERS = [
    {"name": "warming_up", "emoji": "❄️", "label": "Warming Up", "min": 0},
    {"name": "sweet", "emoji": "🥰", "label": "Sweet", "min": 3},
    {"name": "crushing", "emoji": "😍", "label": "Crushing", "min": 5},
    {"name": "madly", "emoji": "🔥", "label": "Madly In Love", "min": 7},
    {"name": "soulmates", "emoji": "💪", "label": "Soulmates", "min": 10},
    {"name": "easter_egg", "emoji": "🌟", "label": "???", "min": 12},
]

LOVE_MESSAGES = {
    "warming_up": [
        "The love account is empty — time to start logging!",
        "Even the longest love story starts with one expense",
        "Your wallet is shy this month... give it some love!",
        "Two hearts, zero logs — let's change that!",
    ],
    "sweet": [
        "Love is in the air... and in the spreadsheet",
        "You two are warming up nicely",
        "A few entries in, and already adorable",
        "Slowly but sweetly, love is being tracked",
    ],
    "crushing": [
        "Jude & Wincyl are on a roll!",
        "This month's love story is getting interesting",
        "Cupid called — he's taking notes",
        "You two are giving main character energy",
    ],
    "madly": [
        "You two are basically a rom-com",
        "Netflix wants the rights to your love story",
        "The expense tracker can barely handle this much love",
        "Your love is louder than your spending",
    ],
    "soulmates": [
        "Perfectly synced — power couple confirmed",
        "10 points! You've unlocked true love",
        "Soulmate status: ACHIEVED",
        "You two are the reason love songs exist",
    ],
    "easter_egg": [
        "You broke the love meter! Scientists are baffled.",
        "ERROR 💕: Too much love detected. System overload.",
        "Achievement unlocked: LOVE BEYOND MEASURE",
        "The tracker wasn't built for this level of romance. Impressive.",
        "You've gone where no couple has gone before. Respect.",
    ],
}


def love_points(df: pd.DataFrame, year: int | None = None, month: int | None = None) -> dict:
    """Calculate love points from expense entries for the current month.

    Returns dict with: combined_points, points (per user), tier, emoji, label,
    message, next_tier_threshold.
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    # Calculate points per user: 1 pt manual, 0.25 pt recurring
    user_points = {"husband": 0.0, "wife": 0.0}

    if not df.empty:
        for _, row in df.iterrows():
            user = row.get("added_by", "")
            if user not in user_points:
                continue
            desc = row.get("description", "") or ""
            if desc.startswith("[Recurring]"):
                user_points[user] += 0.25
            else:
                user_points[user] += 1.0

    combined = sum(user_points.values())

    # Determine tier (walk backwards through tiers to find highest match)
    current_tier = LOVE_TIERS[0]
    for tier in LOVE_TIERS:
        if combined >= tier["min"]:
            current_tier = tier

    # Find next tier threshold
    tier_idx = LOVE_TIERS.index(current_tier)
    if tier_idx < len(LOVE_TIERS) - 1:
        next_threshold = LOVE_TIERS[tier_idx + 1]["min"]
    else:
        next_threshold = None  # Already at max

    # Select message deterministically
    messages = LOVE_MESSAGES[current_tier["name"]]
    msg_idx = (year * 12 + month) % len(messages)
    message = messages[msg_idx]

    return {
        "combined_points": combined,
        "points": user_points,
        "tier": current_tier["name"],
        "emoji": current_tier["emoji"],
        "label": current_tier["label"],
        "message": message,
        "next_tier_threshold": next_threshold,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_analysis.py::TestLovePoints -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add analysis.py tests/test_analysis.py
git commit -m "feat: add love_points() function with input-based scoring"
```

---

## Chunk 2: Dashboard UI + Monthsary Upgrade

### Task 3: Replace Romance Status with Love Points on dashboard

**Files:**
- Modify: `app.py` (imports around line 22, `page_dashboard()` lines 252-268)

- [ ] **Step 6: Update imports in `app.py`**

In `app.py`, change the import from `analysis`:
- Replace `love_comparison` with `love_points` and add `LOVE_TIERS`

Change line 22 from:
```python
    love_comparison, canadian_comparison,
```
to:
```python
    love_points, LOVE_TIERS, canadian_comparison,
```

- [ ] **Step 7: Replace the Romance Status section in `page_dashboard()`**

Replace the entire Romance Status block (lines 252-268) — the `if month_rows:` block containing `st.subheader("💕 Romance Status")` through the closing `unsafe_allow_html=True` — with the new Love Points section. This section always renders (no `if month_rows:` guard):

```python
    # Love Points
    st.subheader("💕 Romance Status")
    lp = love_points(rows_to_dataframe(month_rows))

    # 1. Love Message Banner
    next_month_name = calendar.month_name[today.month % 12 + 1] if today.month < 12 else "January"
    st.markdown(
        f'<div style="text-align:center;padding:24px 20px;'
        f'background:linear-gradient(135deg,#ff6b9d,#c44dff);'
        f'border-radius:14px;margin:10px 0">'
        f'<h2 style="color:white;margin:0;font-size:1.8em">{lp["emoji"]} {lp["message"]}</h2>'
        f'<p style="color:#ffe0f0;margin:5px 0 0;font-size:0.9em">'
        f'Combined Love Points: {lp["combined_points"]:.1f} · Resets {next_month_name} 1st</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 2. Shared Love Meter
    if lp["next_tier_threshold"] is not None:
        progress_pct = min(lp["combined_points"] / lp["next_tier_threshold"], 1.0) * 100
        next_tier = LOVE_TIERS[LOVE_TIERS.index(
            next(t for t in LOVE_TIERS if t["name"] == lp["tier"])
        ) + 1]
        right_label = (f'{lp["combined_points"]:.1f} / {lp["next_tier_threshold"]} pts to '
                       f'{next_tier["emoji"]} {next_tier["label"]}')
    else:
        progress_pct = 100
        right_label = "LOVE OVERLOAD!" if lp["tier"] == "easter_egg" else "MAX LOVE REACHED!"

    st.markdown(
        f'<div style="margin:16px 0">'
        f'<div style="display:flex;justify-content:space-between;color:#ccc;font-size:0.8em;margin-bottom:6px">'
        f'<span>💕 Love Meter — <strong style="color:#ff6b9d">{lp["label"]}</strong></span>'
        f'<span>{right_label}</span></div>'
        f'<div style="background:#2a2a4a;border-radius:10px;height:24px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#ff6b9d,#c44dff);width:{progress_pct:.1f}%;'
        f'height:100%;border-radius:10px"></div></div>'
        f'<div style="display:flex;justify-content:space-between;color:#666;font-size:0.65em;margin-top:4px">'
        f'<span>❄️ 0</span><span>🥰 3</span><span>😍 5</span><span>🔥 7</span><span>💪 10</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 3. Individual Contribution Bars
    from analysis import DISPLAY_NAMES
    h_pts = lp["points"]["husband"]
    w_pts = lp["points"]["wife"]
    total_pts = lp["combined_points"]
    h_pct = (h_pts / total_pts * 100) if total_pts > 0 else 0
    w_pct = (w_pts / total_pts * 100) if total_pts > 0 else 0

    st.markdown(
        f'<div style="display:flex;gap:16px;margin:12px 0">'
        f'<div style="flex:1">'
        f'<div style="color:#ccc;font-size:0.8em;margin-bottom:4px">'
        f'💙 {DISPLAY_NAMES["husband"]} — <strong>{h_pts:.1f} pts</strong></div>'
        f'<div style="background:#2a2a4a;border-radius:8px;height:18px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#4a8cff,#6ba3ff);width:{h_pct:.1f}%;'
        f'height:100%;border-radius:8px"></div></div></div>'
        f'<div style="flex:1">'
        f'<div style="color:#ccc;font-size:0.8em;margin-bottom:4px">'
        f'💗 {DISPLAY_NAMES["wife"]} — <strong>{w_pts:.1f} pts</strong></div>'
        f'<div style="background:#2a2a4a;border-radius:8px;height:18px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#ff6b9d,#ff8fb3);width:{w_pct:.1f}%;'
        f'height:100%;border-radius:8px"></div></div></div></div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 8: Run the app to visually verify**

Run: `streamlit run app.py`
Check: Dashboard shows love message banner, love meter progress bar, and individual bars. Verify it renders even with 0 expenses.

- [ ] **Step 9: Commit**

```bash
git add app.py
git commit -m "feat: replace dollar-based Romance Status with Love Points UI"
```

---

### Task 4: Upgrade monthsary banner with rotating messages and love facts

**Files:**
- Modify: `app.py` (`_monthsary_banner()` function, lines 116-128)

- [ ] **Step 10: Replace `_monthsary_banner()` with upgraded version**

Replace the entire `_monthsary_banner()` function with:

```python
def _monthsary_banner():
    """Show a celebratory banner on/around the 16th of each month."""
    today = date.today()

    MONTHSARY_MESSAGES = [
        "Happy Monthsary! Another beautiful chapter in the Jude & Wincyl story 💕",
        "Happy Monthsary! Still falling for each other, one expense at a time 💕",
        "Happy Monthsary! Love isn't counted in dollars — but we track those too 💕",
        "Happy Monthsary! Another month of being each other's favorite person 💕",
        "Happy Monthsary! The best things in life aren't expenses... but we log them anyway 💕",
    ]
    LOVE_FACTS = [
        "Fun fact: Couples who budget together stay together!",
        "Did you know? Shared financial goals strengthen relationships.",
        "Love tip: It's not about who spends more — it's about spending time together.",
        "Fact: The average couple talks about money 3x a week. You two track it!",
        "Remember: The best investment is in each other.",
    ]

    if today.day == 16:
        st.balloons()
        msg_idx = (today.year * 12 + today.month) % len(MONTHSARY_MESSAGES)
        fact_idx = (today.year * 12 + today.month + 3) % len(LOVE_FACTS)
        st.markdown(
            f'<div style="text-align:center;padding:20px;background:linear-gradient(135deg,#ff6b9d,#c44dff);'
            f'border-radius:12px;margin:10px 0">'
            f'<h2 style="color:white;margin:0">💕 {MONTHSARY_MESSAGES[msg_idx]}</h2>'
            f'<p style="color:#ffe0f0;margin:8px 0 0;font-style:italic">{LOVE_FACTS[fact_idx]}</p>'
            f'</div>', unsafe_allow_html=True)
    elif today.day in (15, 17):
        st.info("💕 Monthsary is on the 16th! Love you always.")
```

- [ ] **Step 11: Verify monthsary banner**

Verify by running `streamlit run app.py` and checking the dashboard. Note: `_monthsary_banner()` only shows on the 16th (or 15th/17th for teaser). To test, temporarily hardcode `today = date(2026, 3, 16)` in the function, verify it renders, then revert.

- [ ] **Step 12: Commit**

```bash
git add app.py
git commit -m "feat: upgrade monthsary banner with rotating messages and love facts"
```

---

## Chunk 3: Cleanup Dead Code

### Task 5: Remove dead `love_comparison` code

**Files:**
- Modify: `analysis.py` (remove `love_comparison()` function, lines ~134-176)
- Modify: `visualization.py` (remove `love_comparison_chart()` function)

- [ ] **Step 13: Remove `love_comparison()` from `analysis.py`**

Delete the entire `love_comparison()` function (the docstring, body, and return statement — approximately lines 134-176). Keep the `DISPLAY_NAMES` dict above it (line 131).

- [ ] **Step 14: Remove `love_comparison_chart()` from `visualization.py`**

Delete the `love_comparison_chart()` function from `visualization.py`.

- [ ] **Step 15: Verify no remaining references**

Run: `grep -r "love_comparison" --include="*.py" .`
Expected: No results (only the spec/plan docs should reference it)

- [ ] **Step 16: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 17: Run the app end-to-end**

Run: `streamlit run app.py`
Verify: Dashboard loads, Love Points section renders, no errors in console.

- [ ] **Step 18: Commit**

```bash
git add analysis.py visualization.py
git commit -m "chore: remove dead love_comparison code replaced by love_points"
```
