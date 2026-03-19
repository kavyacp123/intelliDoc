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
