# Love Points System — Design Spec

## Overview

Replace the current dollar-based Romance Status on the dashboard with an input-based "Love Points" system. Points are earned by logging expenses. The more both users log, the more romantic the dashboard becomes. Resets monthly.

## Points System

- **Manual expense entry** = 1 point (assigned to the user in `added_by`)
- **Recurring expense (auto-generated)** = 0.25 points (passive reward; identified by `[Recurring]` prefix in description)
- Points are calculated from the `expenses` table for the current calendar month
- No new database tables needed — points are derived at query time by counting rows per user per month
- The `added_by` column stores raw usernames (`"husband"`, `"wife"`). Map to display names using `DISPLAY_NAMES` dict in `analysis.py` (Jude/Wincyl) for all UI rendering.
- Recurring expenses credit the person in the recurring expense's `added_by` field (the person it's "for"), not whoever triggered the auto-processing.

## Love Tiers (Combined Points)

| Tier | Points | Emoji |
|------|--------|-------|
| Warming Up | 0–2 | ❄️ |
| Sweet | 3–4 | 🥰 |
| Crushing | 5–6 | 😍 |
| Madly In Love | 7–9 | 🔥 |
| Soulmates | 10–11 | 💪 |
| Hidden Easter Egg | 12+ | 🌟 |

The tier is determined by the **combined** points of both users for the current month.

## Love Messages

Each tier has a pool of rotating messages (mix of sweet & cheesy). A message is selected deterministically using `(year * 12 + month) % len(messages)` so it stays consistent within a month but changes each month.

### Warming Up (❄️) — 0–2 pts
- "The love account is empty — time to start logging!"
- "Even the longest love story starts with one expense"
- "Your wallet is shy this month... give it some love!"
- "Two hearts, zero logs — let's change that!"

### Sweet (🥰) — 3–4 pts
- "Love is in the air... and in the spreadsheet"
- "You two are warming up nicely"
- "A few entries in, and already adorable"
- "Slowly but sweetly, love is being tracked"

### Crushing (😍) — 5–6 pts
- "Jude & Wincyl are on a roll!"
- "This month's love story is getting interesting"
- "Cupid called — he's taking notes"
- "You two are giving main character energy"

### Madly In Love (🔥) — 7–9 pts
- "You two are basically a rom-com"
- "Netflix wants the rights to your love story"
- "The expense tracker can barely handle this much love"
- "Your love is louder than your spending"

### Soulmates (💪) — 10–11 pts
- "Perfectly synced — power couple confirmed"
- "10 points! You've unlocked true love"
- "Soulmate status: ACHIEVED"
- "You two are the reason love songs exist"

### Hidden Easter Egg (🌟) — 12+ pts
- "You broke the love meter! Scientists are baffled."
- "ERROR 💕: Too much love detected. System overload."
- "Achievement unlocked: LOVE BEYOND MEASURE"
- "The tracker wasn't built for this level of romance. Impressive."
- "You've gone where no couple has gone before. Respect."

## Dashboard Layout — Compact (Layout A)

Located in `page_dashboard()`, replacing the current Romance Status section. The Love Points section always renders (even with 0 expenses — shows "Warming Up" encouragement). Remove the current `if month_rows:` guard around Romance Status.

### 1. Love Message Banner
- Gradient background (pink → purple, same as current)
- Shows the tier emoji + rotating message
- Subtitle: "Combined Love Points: X · Resets [next month] 1st"

### 2. Shared Love Meter
- Horizontal progress bar showing combined points progress toward next tier
- Left label: "💕 Love Meter — **[Current Tier]**"
- Right label: "X / Y pts to [Next Tier Emoji] [Next Tier Name]"
- Progress formula: `progress = combined_points / next_tier_threshold` (clamped to 0–1)
  - E.g., 4 points with next tier at 5 = 80% fill
- Tier markers below the bar: ❄️ 0 | 🥰 3 | 😍 5 | 🔥 7 | 💪 10
- At Soulmates or Easter Egg: right label says "MAX LOVE REACHED!" or "LOVE OVERLOAD!"

### 3. Individual Contribution Bars
- Two side-by-side bars
- "💙 Jude — X pts" with blue gradient bar (map from `added_by="husband"`)
- "💗 Wincyl — X pts" with pink gradient bar (map from `added_by="wife"`)
- Bar width proportional to each person's share of combined total (if combined = 0, both bars empty)

## Monthsary Easter Egg (16th of each month)

Upgrade the existing `_monthsary_banner()`:

### On the 16th
- `st.balloons()` (keep existing)
- Rotating celebration messages selected by `(year * 12 + month) % len(messages)`:
  - "Happy Monthsary! Another beautiful chapter in the Jude & Wincyl story 💕"
  - "Happy Monthsary! Still falling for each other, one expense at a time 💕"
  - "Happy Monthsary! Love isn't counted in dollars — but we track those too 💕"
  - "Happy Monthsary! Another month of being each other's favorite person 💕"
  - "Happy Monthsary! The best things in life aren't expenses... but we log them anyway 💕"
- Fun love facts/quotes below the message (rotated monthly):
  - "Fun fact: Couples who budget together stay together!"
  - "Did you know? Shared financial goals strengthen relationships."
  - "Love tip: It's not about who spends more — it's about spending time together."
  - "Fact: The average couple talks about money 3x a week. You two track it!"
  - "Remember: The best investment is in each other."
- Keep the gradient banner styling

### On the 15th and 17th
- Keep the teaser/reminder message (existing behavior)

## Monthly Reset

- Points are derived from the expenses table filtered by current month, so they naturally reset each month
- Query: `WHERE date >= first_of_month AND date <= today` — uses `today` (not end of month) to avoid counting future-dated recurring entries that `process_recurring_expenses()` may have pre-inserted
- The banner shows "Resets [next month name] 1st" as a reminder

## Files to Modify

1. **`analysis.py`**:
   - Replace `love_comparison()` with new `love_points()` function that:
     - Counts entries per user for current month (1 pt manual, 0.25 pt recurring)
     - Returns combined points, per-user points dict, tier name, tier emoji, message
     - Uses `(year * 12 + month) % len(messages)` to select rotating message
   - Keep `love_comparison` import-compatible or remove entirely (see app.py changes)

2. **`app.py`**:
   - Update imports: replace `love_comparison` with `love_points`
   - Replace current Romance Status section in `page_dashboard()` with new Love Points layout
   - Remove the `if month_rows:` guard around the Romance Status section
   - Add love meter HTML (progress bar + tier markers) via `st.markdown(unsafe_allow_html=True)`
   - Add individual contribution bars
   - Upgrade `_monthsary_banner()` with rotating messages and love facts

3. **`visualization.py`** — Remove dead `love_comparison_chart()` function (no longer called after this change)

## Files NOT Modified

- `database.py` — no schema changes, points derived from existing `expenses` table
- `validation.py` — no changes needed

## Edge Cases

- **No expenses this month**: Show "Warming Up" tier with encouraging message (always render section)
- **Only one user has entries**: Still show both bars, one at 0
- **Exactly 10–11 points**: Soulmates tier (not Easter Egg — that's 12+)
- **First of month**: Naturally 0 points, fresh start message
- **Both users at 0 points**: Both bars empty, combined meter at 0%
