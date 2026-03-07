"""
IntelliDoc Worker — Financial Validation (Stage 8)

Applies business rules to extracted records to flag inconsistencies.
Records that fail validation are marked as 'needs_review'.

Rules:
  1. grand_total ≈ subtotal + taxes (within 5% tolerance)
  2. Date must be valid and not in the far future
  3. Confidence threshold must be above minimum
  4. At least one financial field must be extracted
"""

from datetime import datetime, timedelta
from typing import Optional


# ─── Configuration ──────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.7
TOTAL_TOLERANCE = 0.05   # 5% tolerance for total vs sum-of-parts
MAX_FUTURE_DAYS = 30     # dates more than 30 days in the future are suspicious


def validate_record(record: dict, confidence: float = 1.0) -> dict:
    """
    Validate a normalised financial record.

    Args:
        record: Normalised dict with invoice_date, grand_total, taxes, etc.
        confidence: Average OCR confidence score for this page.

    Returns:
        Dict with:
            - is_valid: bool
            - issues: list of string descriptions of problems
            - status: "completed" or "needs_review"
    """
    issues = []

    # Rule 1 — Total consistency check
    total_issue = _check_total_consistency(record)
    if total_issue:
        issues.append(total_issue)

    # Rule 2 — Date validity
    date_issue = _check_date(record.get("invoice_date"))
    if date_issue:
        issues.append(date_issue)

    # Rule 3 — Confidence threshold
    if confidence < CONFIDENCE_THRESHOLD:
        issues.append(
            f"Low OCR confidence: {confidence:.2f} (threshold: {CONFIDENCE_THRESHOLD})"
        )

    # Rule 4 — At least one financial field must be present
    financial_fields = ["subtotal", "cgst", "sgst", "igst", "grand_total"]
    has_financial = any(record.get(f) is not None for f in financial_fields)
    if not has_financial:
        issues.append("No financial fields extracted.")

    is_valid = len(issues) == 0
    status = "completed" if is_valid else "needs_review"

    if issues:
        print(f"  ⚠️  Validation issues: {issues}")

    return {
        "is_valid": is_valid,
        "issues": issues,
        "status": status,
    }


def _check_total_consistency(record: dict) -> Optional[str]:
    """
    Check if grand_total ≈ subtotal + cgst + sgst + igst.
    Only runs if enough fields are present to compare.
    """
    grand_total = record.get("grand_total")
    subtotal = record.get("subtotal")
    cgst = record.get("cgst") or 0
    sgst = record.get("sgst") or 0
    igst = record.get("igst") or 0

    if grand_total is None or subtotal is None:
        return None  # Not enough data to validate

    expected = subtotal + cgst + sgst + igst

    if expected == 0:
        return None

    diff_pct = abs(grand_total - expected) / expected

    if diff_pct > TOTAL_TOLERANCE:
        return (
            f"Total mismatch: grand_total={grand_total:.2f} vs "
            f"computed={expected:.2f} (diff={diff_pct:.1%})"
        )

    return None


def _check_date(date_str: Optional[str]) -> Optional[str]:
    """Validate that the invoice date is a real, non-future date."""
    if not date_str:
        return None

    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return f"Invalid date format: {date_str}"

    # Check for unreasonably far future dates
    max_date = datetime.now() + timedelta(days=MAX_FUTURE_DAYS)
    if parsed > max_date:
        return f"Date is in the future: {date_str}"

    # Check for unreasonably old dates (before 2000)
    if parsed.year < 2000:
        return f"Date is suspiciously old: {date_str}"

    return None
