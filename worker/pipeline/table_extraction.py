"""
IntelliDoc Worker — Table Extraction (Stage 6)

Uses Camelot to detect and extract table structures from PDF pages.
Extracts line items (description, quantity, rate, amount).

Falls back to OCR-based table detection if Camelot can't find tables.
"""

import os
import tempfile

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    print("  ⚠️  Camelot not available — table extraction disabled.")


def extract_tables_from_pdf(pdf_path: str, page_number: int = 1) -> list[list[dict]]:
    """
    Extract tables from a specific page of a PDF file using Camelot.

    Args:
        pdf_path: Absolute path to the PDF file.
        page_number: 1-indexed page number.

    Returns:
        List of tables, each table is a list of row dicts.
        e.g. [[{"description": "Widget", "qty": "10", "rate": "500", "amount": "5000"}]]
    """
    if not CAMELOT_AVAILABLE:
        return []

    try:
        # Camelot uses 1-indexed page strings
        tables = camelot.read_pdf(
            pdf_path,
            pages=str(page_number),
            flavor="lattice",  # Try lattice (bordered tables) first
        )

        if not tables or len(tables) == 0:
            # Fall back to stream (borderless tables)
            tables = camelot.read_pdf(
                pdf_path,
                pages=str(page_number),
                flavor="stream",
            )

        if not tables or len(tables) == 0:
            return []

        result = []
        for table in tables:
            rows = _parse_table(table.df)
            if rows:
                result.append(rows)

        print(f"  📊 Extracted {len(result)} table(s) from page {page_number}.")
        return result

    except Exception as e:
        print(f"  ⚠️  Camelot table extraction failed: {e}")
        return []


def _parse_table(df) -> list[dict]:
    """
    Parse a pandas DataFrame from Camelot into structured line-item dicts.
    Tries to map columns to: description, quantity, rate, amount.
    """
    if df.empty or len(df) < 2:  # Need at least header + 1 row
        return []

    # Use the first row as headers
    headers = [str(h).strip().lower() for h in df.iloc[0]]

    # Map headers to canonical names
    col_map = _map_columns(headers)

    if not col_map:
        # If we can't identify columns, return raw rows
        rows = []
        for i in range(1, len(df)):
            row_data = {f"col_{j}": str(df.iloc[i, j]).strip() for j in range(len(headers))}
            rows.append(row_data)
        return rows

    # Extract structured rows
    rows = []
    for i in range(1, len(df)):
        row = {}
        for canonical, col_idx in col_map.items():
            value = str(df.iloc[i, col_idx]).strip()
            if value and value.lower() not in ("", "nan", "none"):
                row[canonical] = value
        if row:
            rows.append(row)

    return rows


def _map_columns(headers: list[str]) -> dict:
    """
    Map detected column headers to canonical names.
    Returns {canonical_name: column_index} or empty dict if no match.
    """
    mapping = {}

    col_patterns = {
        "description": ["description", "particulars", "item", "product", "service", "details"],
        "quantity": ["qty", "quantity", "units", "nos"],
        "rate": ["rate", "price", "unit price", "unit rate"],
        "amount": ["amount", "total", "value", "net amount"],
    }

    for i, header in enumerate(headers):
        for canonical, patterns in col_patterns.items():
            if canonical not in mapping:
                for pattern in patterns:
                    if pattern in header:
                        mapping[canonical] = i
                        break

    return mapping
