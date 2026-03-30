"""
Parser utility helpers.

Functions for normalizing column names, inferring data types from
pandas DataFrames, and other file-processing primitives.
"""

import re
from typing import List, Tuple

import pandas as pd


def normalize_column_name(name: str) -> str:
    """
    Normalize a raw column name for safe use in SQL.

    - Lowercase
    - Replace whitespace and special chars with underscores
    - Collapse consecutive underscores
    - Ensure the name starts with a letter
    """
    name = str(name).lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    if not name or not name[0].isalpha():
        name = "col_" + name
    return name


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename all columns in a DataFrame to their normalized form.

    Returns a new DataFrame (does not mutate the original).
    """
    mapping = {col: normalize_column_name(col) for col in df.columns}
    return df.rename(columns=mapping)


def _find_header_row(df: pd.DataFrame, max_rows: int = 20) -> int:
    """
    Scans the first 'max_rows' to find the actual header row.
    Assumes the header row is the first row with a high density of non-null string values.
    Returns the index of the header row, or 0 if not found.
    """
    if df.empty:
        return 0
        
    best_row_idx = 0
    max_density = -1
    
    # Also check the columns themselves (row -1)
    col_density = sum(1 for c in df.columns if not str(c).startswith("Unnamed:") and pd.notna(c))
    if col_density > 0:
        max_density = col_density / len(df.columns)
        best_row_idx = -1 # Indicates the current df.columns are the actual headers
        
    for i in range(min(len(df), max_rows)):
        row = df.iloc[i]
        # Count non-null values that look like strings (typical for headers)
        valid_cells = sum(1 for val in row if pd.notna(val) and isinstance(val, str) and str(val).strip())
        density = valid_cells / len(df.columns)
        
        # If we find a row with > 50% string density or the highest density so far
        if density > max_density and density > 0.1:
            max_density = density
            best_row_idx = i
            
        # If we hit a very dense row (e.g.,> 80% filled), we can confidently say it's the header
        if density >= 0.8:
            break
            
    return best_row_idx

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans up a raw DataFrame by:
    1. Finding the true header row (skipping titles/metadata above it).
    2. Dropping completely empty rows and columns.
    3. Normalizing column names and handling remaining 'Unnamed' columns.
    """
    if df.empty:
        return df
        
    # 1. Strip completely empty rows and cols first
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
    
    if df.empty:
        return df

    # 2. Find header row
    header_idx = _find_header_row(df)
    
    if header_idx > -1:
        # Promote the found row to headers
        new_headers = df.iloc[header_idx].values
        df.columns = new_headers
        # Drop the header row and everything above it
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
        
    # 3. Strip empty rows/cols again (just in case they were only empty below the new header)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
    
    # 3.5. Strip 'Grand Total' or 'Total' summary rows at the bottom
    if not df.empty:
        # Check the last 10 rows for summary text
        bottom_n = min(10, len(df))
        drop_indices = []
        for i in range(len(df) - bottom_n, len(df)):
            row = df.iloc[i]
            # Check the first 5 columns for 'total' string
            for val in row[:5]:
                if isinstance(val, str):
                    lower_val = val.lower().strip()
                    if lower_val == "total" or lower_val == "grand total" or lower_val.startswith("total:"):
                        drop_indices.append(df.index[i])
                        break
        if drop_indices:
            df = df.drop(index=drop_indices)

    
    # 4. Clean column names
    clean_cols = []
    unnamed_count = 1
    for col in df.columns:
        if pd.isna(col) or str(col).startswith("Unnamed:"):
            # It's an unnamed column. If it has data, give it a generic name
            clean_cols.append(f"column_{unnamed_count}")
            unnamed_count += 1
        else:
            clean_cols.append(str(col))
            
    df.columns = clean_cols
    
    # 5. Normalize using existing logic
    return normalize_columns(df)

def flatten_json_to_df(data: list) -> pd.DataFrame:
    """
    Flattens a list of nested JSON objects into a flat Pandas DataFrame.
    """
    return pd.json_normalize(data)

def infer_column_types(df: pd.DataFrame) -> List[Tuple[str, str]]:
    """
    Infer simplified type labels for each column in a DataFrame.

    Returns:
        List of (column_name, type_label) tuples.
        type_label is one of: "int", "float", "datetime", "string"
    """
    result = []
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            result.append((col, "int"))
        elif pd.api.types.is_float_dtype(dtype):
            result.append((col, "float"))
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            result.append((col, "datetime"))
        else:
            # Attempt to parse as datetime
            try:
                pd.to_datetime(df[col], format="mixed", dayfirst=False)
                result.append((col, "datetime"))
            except (ValueError, TypeError):
                result.append((col, "string"))
    return result
