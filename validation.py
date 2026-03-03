"""Input validation for expense entries."""

from datetime import date

MAX_AMOUNT = 100_000.0
MAX_DESCRIPTION_LENGTH = 500


def validate_expense(
    amount: float,
    category: str,
    description: str,
    existing_expenses: list[dict] | None = None,
    exp_date: date | None = None,
    confirm_duplicate: bool = False,
) -> tuple[bool, str]:
    """Validate an expense entry.

    Returns (is_valid, message).  When a duplicate is detected the message
    starts with "DUPLICATE:" — the caller should show a warning and let the
    user submit again with *confirm_duplicate=True* to bypass.
    """
    # Amount checks
    if amount <= 0:
        return False, "Amount must be positive."
    if amount > MAX_AMOUNT:
        return False, f"Amount cannot exceed ${MAX_AMOUNT:,.2f}."

    # Description checks
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return False, f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters."
    if category == "Others" and not description.strip():
        return False, "Description is required for 'Others' category."

    # Duplicate check
    if not confirm_duplicate and existing_expenses and exp_date:
        for row in existing_expenses:
            if (row["date"] == exp_date.isoformat()
                    and abs(row["amount"] - round(amount, 2)) < 0.01
                    and row["category"] == category):
                return False, (
                    f"DUPLICATE: A similar expense (${row['amount']:,.2f} in {category}) "
                    f"already exists on {exp_date}. Submit again to confirm."
                )

    return True, ""
