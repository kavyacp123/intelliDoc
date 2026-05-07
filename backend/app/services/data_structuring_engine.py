"""
Universal Data Structuring Engine.

Detects the structure of uploaded tabular data (normal tables, multi-line row transactions)
and converts it into a flattened, normalized schema ready for SQL analytics.
"""

import logging
import re
import pandas as pd
import numpy as np
from typing import Dict, Any
from pandas.api.types import is_datetime64_any_dtype

logger = logging.getLogger(__name__)


def _resolve_column_name(df: pd.DataFrame, target: str) -> str | None:
    """Find a column by case-insensitive name match."""
    target = target.strip().lower()
    for col in df.columns:
        if str(col).strip().lower() == target:
            return col
    return None


def _row_is_effectively_empty(row: pd.Series) -> bool:
    for val in row.values:
        if pd.isna(val):
            continue
        if isinstance(val, str) and not val.strip():
            continue
        return False
    return True


def _looks_like_summary_row(row: pd.Series) -> bool:
    for val in row.values[:5]:
        if isinstance(val, str):
            lowered = val.strip().lower()
            if lowered in {"total", "grand total"} or lowered.startswith("total:"):
                return True
    return False


def _is_parent_date_value(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if is_datetime64_any_dtype(type(value)):
        return True
    parsed = pd.to_datetime([value], errors="coerce")
    return bool(parsed.notna()[0])


def _is_sales_register_parent(row: pd.Series, date_col: str) -> bool:
    return _is_parent_date_value(row.get(date_col))


def _is_sales_register_child(
    row: pd.Series,
    date_col: str,
    particulars_col: str,
    all_columns: list[str],
) -> bool:
    date_empty = pd.isna(row.get(date_col)) or str(row.get(date_col)).strip() in {"", "nan", "NaT"}
    particulars_val = row.get(particulars_col)
    particulars_filled = pd.notna(particulars_val) and str(particulars_val).strip() != ""
    other_cols = [c for c in all_columns if c not in (date_col, particulars_col)]
    all_others_empty = all(pd.isna(row.get(col)) for col in other_cols)
    return date_empty and particulars_filled and all_others_empty


def is_sales_register_parent_child(df: pd.DataFrame) -> bool:
    """
    Detect the parent-child sales register pattern seen in SR_22-23 type files.

    Parent rows contain transaction context (especially Date), while child rows
    only contain a product name under Particulars.
    """
    if df.empty or len(df.columns) < 2:
        return False

    date_col = _resolve_column_name(df, "Date")
    particulars_col = _resolve_column_name(df, "Particulars")
    if not date_col or not particulars_col:
        return False

    parent_count = 0
    child_count = 0
    sampled_rows = 0

    for _, row in df.iterrows():
        if _row_is_effectively_empty(row) or _looks_like_summary_row(row):
            continue
        sampled_rows += 1
        if _is_sales_register_parent(row, date_col):
            parent_count += 1
        elif _is_sales_register_child(row, date_col, particulars_col, list(df.columns)):
            child_count += 1

    if sampled_rows == 0 or parent_count == 0 or child_count == 0:
        return False

    child_ratio = child_count / max(sampled_rows, 1)
    return child_ratio >= 0.10


def flatten_sales_register_parent_child(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten SR-style parent/child transaction sheets into one row per product.

    Parent row:
      Date + transaction metadata
    Child row:
      only Particulars populated -> represents a product/item
    """
    date_col = _resolve_column_name(df, "Date")
    particulars_col = _resolve_column_name(df, "Particulars")
    if not date_col or not particulars_col:
        return df

    flat_rows = []
    current_parent: Dict[str, Any] | None = None
    current_children: list[str] = []

    def _parse_payment_days(raw_value: Any) -> float | None:
        if pd.isna(raw_value):
            return None
        text = str(raw_value).strip().lower()
        if not text:
            return None
        if "advance" in text:
            return 0.0
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        return float(match.group(1)) if match else None

    def _numeric_value(parent: Dict[str, Any], candidates: list[str]) -> float:
        for candidate in candidates:
            actual = _resolve_column_name(pd.DataFrame(columns=parent.keys()), candidate)
            if actual is None:
                continue
            value = parent.get(actual)
            if pd.isna(value):
                continue
            try:
                return float(value)
            except Exception:
                continue
        return 0.0

    def _emit_parent_rows(parent: Dict[str, Any], children: list[str]) -> None:
        if parent is None:
            return

        product_names = [child for child in children if child.strip()]
        if not product_names:
            particulars_val = parent.get(particulars_col)
            if pd.notna(particulars_val) and str(particulars_val).strip():
                product_names = [str(particulars_val).strip()]

        if not product_names:
            return

        line_item_count = len(product_names)
        gross_total = _numeric_value(parent, ["Gross Total"])
        net_sales = _numeric_value(parent, ["Sales", "Export Sales", "Sales  Inside Guj GST", "Sales  Outside Guj GST"])
        allocated_gross_total = gross_total / line_item_count if line_item_count else 0.0
        allocated_revenue = (net_sales or gross_total) / line_item_count if line_item_count else 0.0
        payment_days = _parse_payment_days(parent.get(_resolve_column_name(pd.DataFrame(columns=parent.keys()), "Terms of Payment") or "Terms of Payment"))

        for product_name in product_names:
            merged = parent.copy()
            merged["Product"] = product_name
            merged["Line Item Count"] = line_item_count
            merged["Line Quantity"] = 1
            merged["Allocated Gross Total"] = allocated_gross_total
            merged["Allocated Revenue"] = allocated_revenue
            if payment_days is not None:
                merged["Payment Term Days"] = payment_days
            flat_rows.append(merged)

    for _, row in df.iterrows():
        if _row_is_effectively_empty(row) or _looks_like_summary_row(row):
            continue

        row_dict = row.to_dict()

        if _is_sales_register_parent(row, date_col):
            if current_parent is not None:
                _emit_parent_rows(current_parent, current_children)
            current_parent = row_dict.copy()
            current_children = []
            continue

        if _is_sales_register_child(row, date_col, particulars_col, list(df.columns)) and current_parent is not None:
            current_children.append(str(row.get(particulars_col)).strip())
            continue

        if current_parent is not None and pd.notna(row.get(particulars_col)) and str(row.get(particulars_col)).strip():
            fallback_product = str(row.get(particulars_col)).strip()
            if fallback_product:
                current_children.append(fallback_product)

    if current_parent is not None:
        _emit_parent_rows(current_parent, current_children)

    if not flat_rows:
        return df

    df_flat = pd.DataFrame(flat_rows)

    priority_cols = [col for col in ["Date", "Product"] if col in df_flat.columns]
    other_cols = [c for c in df_flat.columns if c not in priority_cols]
    df_flat = df_flat[priority_cols + other_cols]

    if "Date" in df_flat.columns:
        df_flat["Date"] = pd.to_datetime(df_flat["Date"], errors="coerce").dt.date

    if "Product" in df_flat.columns:
        df_flat = df_flat[df_flat["Product"].notna() & (df_flat["Product"].astype(str).str.strip() != "")]

    df_flat.reset_index(drop=True, inplace=True)
    return df_flat

# =========================
# 1. STRUCTURE DETECTION
# =========================
def detect_structure(df: pd.DataFrame) -> str:
    """Classifies the DataFrame structure using missing data patterns."""
    if df.empty:
        return "unknown"

    if is_sales_register_parent_child(df):
        return "sales_register_parent_child"
        
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
        numeric_like = {
            "revenue", "quantity", "cost", "sales", "price",
            "gross_total", "allocated_gross_total", "allocated_revenue",
            "line_item_count", "line_quantity", "payment_term_days",
        }
        if col in numeric_like or 'amount' in col:
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
    if structure == "sales_register_parent_child":
        df = flatten_sales_register_parent_child(df)
    elif structure == "tabular":
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
