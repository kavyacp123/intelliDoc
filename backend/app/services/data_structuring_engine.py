"""
Universal Data Structuring Engine.

Detects the structure of uploaded tabular data (normal tables, multi-line row transactions)
and converts it into a flattened, normalized schema ready for SQL analytics.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any

logger = logging.getLogger(__name__)

# =========================
# 1. STRUCTURE DETECTION
# =========================
def detect_structure(df: pd.DataFrame) -> str:
    """Classifies the DataFrame structure using missing data patterns."""
    if df.empty:
        return "unknown"
        
    total_cells = df.shape[0] * df.shape[1]
    if total_cells == 0:
        return "unknown"
        
    null_ratio = df.isna().sum().sum() / total_cells

    # Highly filled grid -> typical tabular
    if null_ratio < 0.2:
        return "tabular"

    # Multi-line detection: Check if the first column (often date/ID) is heavily null
    # compared to other columns (like products)
    if df.shape[1] > 0 and df.iloc[:, 0].notna().sum() < df.shape[0] * 0.7:
        return "multi_line"

    return "unknown"

# =========================
# 2. NUMERIC EXTRACTION
# =========================
def extract_numeric(row: pd.Series) -> float:
    """Attempts to find the highest valid numeric value in a poorly structured row."""
    for val in reversed(list(row.values)):
        try:
            # Skip dates or generic strings
            if isinstance(val, (int, float)):
                if val > 0:
                    return float(val)
            elif isinstance(val, str):
                cleaned = val.replace(',', '').replace('$', '').strip()
                if cleaned and cleaned != '0':
                    num = float(cleaned)
                    if num > 0:
                        return num
        except Exception:
            continue
    return 0.0

# =========================
# 3. MULTI-LINE PARSER
# =========================
def parse_multiline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parses datasets where transactions span multiple rows.
    e.g. 
    Row 1: Date | Company | null
    Row 2: null | null    | Product A | Price
    Row 3: null | null    | Product B | Price
    """
    structured_rows = []
    current_transaction: Dict[str, Any] = {}
    
    # Try to identify which columns contain what by position or name.
    # We assume a pattern often seen in accounting books.
    
    # Let's inspect the headers or first row context
    col_names = [str(c).lower() for c in df.columns]
    
    date_col_idx = 0
    company_col_idx = 1
    
    # Attempt to locate named columns if they exist
    for idx, c in enumerate(col_names):
        if 'date' in c:
            date_col_idx = idx
        elif 'particulars' in c or 'company' in c or 'name' in c:
            company_col_idx = idx

    for _, row in df.iterrows():
        date = row.iloc[date_col_idx] if len(row) > date_col_idx else None
        particulars = row.iloc[company_col_idx] if len(row) > company_col_idx else None
        
        # Determine if this row starts a new transaction block (has date or date-like value)
        is_new_txn = False
        if pd.notna(date) and str(date).strip() != '':
            # It's a new block (e.g. date usually only appears on the first line)
            is_new_txn = True
        
        # Heuristic 2: If particulars is something like "By " or "To " it might be an accounting line
        
        if is_new_txn:
            # Emit old
            if current_transaction and current_transaction.get("products"):
                for product, sales in current_transaction["products"]:
                    structured_rows.append({
                        "date": current_transaction["date"],
                        "company": current_transaction["company"],
                        "product": product,
                        "sales": sales
                    })

            # Start new
            current_transaction = {
                "date": date,
                "company": particulars,
                "products": []
            }
        else:
            # Product line! 
            # The product is likely in the particulars column if there's no date
            if current_transaction and pd.notna(particulars) and str(particulars).strip():
                # Value extraction
                sales_val = extract_numeric(row)
                current_transaction["products"].append((particulars, sales_val))

    # Catch the last one
    if current_transaction and current_transaction.get("products"):
         for product, sales in current_transaction["products"]:
             structured_rows.append({
                 "date": current_transaction["date"],
                 "company": current_transaction["company"],
                 "product": product,
                 "sales": sales
             })

    if not structured_rows:
        # Fallback if no multi-line structure found, just return original df
        return df

    return pd.DataFrame(structured_rows)

# =========================
# 4. TABULAR CLEANER
# =========================
def clean_tabular(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans up a standard table. Based on the existing parser_utils logic.
    """
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    if df.empty:
        return df

    # Basic normalization applied at the end. Here we just ensure we drop fully empty stuff
    return df

# =========================
# 5. COLUMN NORMALIZATION
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Maps column names to common business types and standardizes naming format.
    """
    import re
    
    # 1. Standardize format
    clean_cols = []
    unnamed_count = 1
    for col in df.columns:
        if pd.isna(col) or str(col).startswith("Unnamed:"):
            clean_cols.append(f"column_{unnamed_count}")
            unnamed_count += 1
        else:
            name = str(col).lower().strip()
            name = re.sub(r"[^a-z0-9_]", "_", name)
            name = re.sub(r"_+", "_", name)
            name = name.strip("_")
            if not name or not name[0].isalpha():
                name = "col_" + name
            clean_cols.append(name)
            
    df.columns = clean_cols

    # 2. Map to common terms
    column_map = {
        "particulars": "company",
        "buyer": "customer",
        "amount": "revenue",
        "sales": "revenue",
        "value": "revenue",
        "qty": "quantity",
    }
    
    new_names = {}
    mapped_targets = set()
    
    # First pass: direct matches
    for col in df.columns:
        if col in column_map:
            target = column_map[col]
            if target not in mapped_targets and target not in df.columns:
                new_names[col] = target
                mapped_targets.add(target)

    # Second pass: substring matches
    for col in df.columns:
        if col not in new_names:
            for key, target in column_map.items():
                if key in col and target not in mapped_targets and target not in df.columns:
                    new_names[col] = target
                    mapped_targets.add(target)
                    break

    if new_names:
        df = df.rename(columns=new_names)
        
    # Extra safety: Ensure all columns are unique after normalization
    if len(df.columns) != len(set(df.columns)):
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique(): 
            cols[cols[cols == dup].index.values.tolist()] = [dup + '_' + str(i) if i != 0 else dup for i in range(sum(cols == dup))]
        df.columns = cols

    return df

# =========================
# 6. DATA CLEANING
# =========================
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans up internal data types and structural integrity."""
    df = df.dropna(how="all")

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Clean any string numeric columns (e.g. currency signs)
    for col in df.columns:
        if col in ("revenue", "quantity", "cost", "sales", "price") or 'amount' in col:
             # Try numeric cast
             df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

# =========================
# 7. MAIN PIPELINE
# =========================
def structure_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    The Universal Data Structuring Entrypoint.
    Takes an unformatted raw DataFrame and outputs a SQL-ready flattened table.
    """
    if df.empty:
        return df

    # Find the header row if the table was pasted with junk above it
    from app.utils.parser_utils import _find_header_row
    header_idx = _find_header_row(df)
    
    if header_idx > -1:
        new_headers = df.iloc[header_idx].values
        df.columns = new_headers
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
        
    # Re-evaluate empty rows
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)

    structure = detect_structure(df)
    logger.info(f"Detected dataset structure: {structure}")

    # Process based on type
    if structure == "tabular":
        df = clean_tabular(df)
    elif structure == "multi_line":
        df = parse_multiline(df)
    else:
        # fallback (still try multiline)
        logger.info("Structure unknown, attempting multiline parser fallback.")
        df = parse_multiline(df)

    # Final normalization passes
    df = normalize_columns(df)
    df = clean_data(df)

    return df
