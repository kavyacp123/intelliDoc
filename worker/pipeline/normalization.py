"""
IntelliDoc Worker — Data Normalization (Stage 7)

Cleans and normalises extracted financial values:
- Currency strings → numeric (₹22,222.00 → 22222.00)
- Date strings → ISO format (28-08-2025 → 2025-08-28)
- Vendor names → cleaned strings
"""

import re
from datetime import datetime
from typing import Optional


def normalize_currency(value: str) -> Optional[float]:
    """
    Convert a currency string to a float.

    Handles: ₹22,222.00 | Rs. 1,20,000 | $1,234.56 | 22222 | INR 50000

    Returns None if the input can't be parsed.
    """
    if not value or not isinstance(value, str):
        return None

    # Remove currency symbols, "Rs", "INR", commas, spaces
    cleaned = value
    cleaned = re.sub(r"[₹$€£]", "", cleaned)
    cleaned = re.sub(r"(?i)Rs\.?", "", cleaned)
    cleaned = re.sub(r"(?i)INR", "", cleaned)
    cleaned = re.sub(r"[,\s]", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    # Extract the numeric portion (handles trailing text like "/-")
    match = re.search(r"[\d]+\.?\d*", cleaned)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def normalize_date(value: str) -> Optional[str]:
    """
    Convert various date formats to ISO YYYY-MM-DD.

    Handles: 28-08-2025 | 28/08/2025 | 2025-08-28 | 28 Aug 2025
    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()

    # List of formats to try (most specific first)
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",       # DD-MM-YYYY
        "%Y-%m-%d", "%Y/%m/%d",                     # YYYY-MM-DD (ISO)
        "%d-%m-%y", "%d/%m/%y",                     # DD-MM-YY
        "%d %b %Y", "%d %B %Y",                     # 28 Aug 2025
        "%b %d, %Y", "%B %d, %Y",                   # Aug 28, 2025
        "%d-%b-%Y", "%d-%B-%Y",                     # 28-Aug-2025
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_vendor(value: str) -> Optional[str]:
    """Clean vendor name: trim whitespace, collapse multi-spaces."""
    if not value or not isinstance(value, str):
        return None

    cleaned = re.sub(r"\s+", " ", value).strip()
    # Remove trailing punctuation
    cleaned = cleaned.rstrip(":.-–")
    return cleaned if len(cleaned) >= 2 else None


def normalize_record(raw: dict) -> dict:
    """
    Normalise a full extracted record dict.

    Input:  {"invoice_date": "28-08-2025", "grand_total": "₹22,222.00", ...}
    Output: {"invoice_date": "2025-08-28", "grand_total": 22222.00, ...}
    """
    normalised = {}

    # Date fields
    for field in ["invoice_date"]:
        if field in raw and raw[field]:
            normalised[field] = normalize_date(raw[field])

    # Currency fields
    for field in ["subtotal", "cgst", "sgst", "igst", "grand_total"]:
        if field in raw and raw[field]:
            normalised[field] = normalize_currency(raw[field])

    # String fields
    for field in ["vendor"]:
        if field in raw and raw[field]:
            normalised[field] = normalize_vendor(raw[field])

    # Pass-through fields
    for field in ["invoice_number"]:
        if field in raw and raw[field]:
            normalised[field] = str(raw[field]).strip()

    return normalised
