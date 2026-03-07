"""
IntelliDoc Worker — Key-Value Extraction (Stage 5)

Extracts key-value pairs from OCR results using spatial proximity analysis.
Algorithm: find keyword → locate nearest value box → pair them.

This mimics the approach used by AWS Textract's key-value detection.
"""

import re
from typing import Optional


# ─── Keyword Configuration ──────────────────────────────────────────────────────
# Maps canonical field names to their possible label variants found on invoices.
# ────────────────────────────────────────────────────────────────────────────────

FIELD_KEYWORDS = {
    "invoice_number": [
        "invoice no", "invoice number", "invoice #", "inv no", "inv. no",
        "bill no", "bill number", "ref no", "reference no",
    ],
    "invoice_date": [
        "date", "invoice date", "inv date", "bill date", "dated",
    ],
    "vendor": [
        "vendor", "supplier", "from", "bill from", "sold by",
        "company", "billed by", "seller",
    ],
    "subtotal": [
        "subtotal", "sub total", "sub-total", "taxable amount",
        "taxable value", "net amount",
    ],
    "cgst": ["cgst", "central gst", "central tax"],
    "sgst": ["sgst", "state gst", "state tax"],
    "igst": ["igst", "integrated gst", "integrated tax"],
    "grand_total": [
        "grand total", "total", "total amount", "amount due",
        "total payable", "net payable", "balance due", "amount payable",
    ],
}


def extract_key_values(ocr_results: list[dict]) -> dict:
    """
    Extract key-value pairs from OCR results using two strategies:

    1. Spatial proximity — find a keyword box and pair it with the
       nearest value box (to the right or below).
    2. Inline parsing — if the keyword and value are in the same text
       block (e.g. "Invoice No: 107"), split on the delimiter.

    Args:
        ocr_results: List of OCR dicts with text, bbox, confidence.

    Returns:
        Dict mapping canonical field names to extracted values.
        e.g. {"invoice_number": "107", "grand_total": "22222.00"}
    """
    extracted = {}

    for field_name, keywords in FIELD_KEYWORDS.items():
        value = _find_field_value(ocr_results, keywords)
        if value:
            extracted[field_name] = value

    print(f"  🔑 Extracted {len(extracted)} key-value pairs: {list(extracted.keys())}")
    return extracted


def _find_field_value(ocr_results: list[dict], keywords: list[str]) -> Optional[str]:
    """
    For a set of keywords, search through OCR results and try to find
    the corresponding value using two strategies.
    """
    for i, block in enumerate(ocr_results):
        text_lower = block["text"].lower().strip()

        for keyword in keywords:
            # Strategy 1: Inline — keyword and value in the same block
            # e.g. "Invoice No : 107" or "Date: 28-08-2025"
            pattern = re.compile(
                rf"{re.escape(keyword)}\s*[:\-–]?\s*(.+)",
                re.IGNORECASE,
            )
            match = pattern.search(block["text"])
            if match:
                value = match.group(1).strip()
                if value:
                    return value

            # Strategy 2: Spatial — keyword is a standalone label,
            # value is in the nearest box to the right or below
            if text_lower == keyword or text_lower == keyword + ":":
                nearest = _find_nearest_value(block, i, ocr_results)
                if nearest:
                    return nearest

    return None


def _find_nearest_value(
    key_block: dict,
    key_index: int,
    ocr_results: list[dict],
) -> Optional[str]:
    """
    Find the nearest OCR text block to the right of or below the key block.
    Uses spatial distance between bounding box centres.
    """
    kx1, ky1, kx2, ky2 = key_block["bbox"]
    key_cx = (kx1 + kx2) / 2
    key_cy = (ky1 + ky2) / 2

    best_value = None
    best_distance = float("inf")

    for j, candidate in enumerate(ocr_results):
        if j == key_index:
            continue

        cx1, cy1, cx2, cy2 = candidate["bbox"]
        cand_cx = (cx1 + cx2) / 2
        cand_cy = (cy1 + cy2) / 2

        # Only consider candidates to the right or below the key
        if cand_cx < kx1 - 20:  # too far left
            continue

        # Vertical alignment check — must be roughly on the same line
        # or just below (within 2× the key's height)
        key_height = ky2 - ky1
        vertical_gap = abs(cand_cy - key_cy)

        # Prefer values on the same line (to the right)
        if vertical_gap < key_height * 0.5 and cand_cx > kx2:
            distance = cand_cx - kx2  # horizontal distance
        elif cand_cy > ky2 and abs(cand_cx - key_cx) < (kx2 - kx1) * 2:
            distance = (cand_cy - ky2) * 2  # vertical (penalised)
        else:
            continue

        if distance < best_distance:
            best_distance = distance
            best_value = candidate["text"].strip()

    return best_value
