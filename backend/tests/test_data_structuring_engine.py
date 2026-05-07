import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.data_structuring_engine import (
    flatten_sales_register_parent_child,
    is_sales_register_parent_child,
    structure_dataframe,
)


def test_sales_register_parent_child_is_detected():
    df = pd.DataFrame(
        [
            ["Date", "Particulars", "Buyer", "Amount"],
            ["2024-01-01", "Invoice 1", "Acme LLC", 1200],
            [None, "Product A", None, None],
            [None, "Product B", None, None],
            ["2024-01-02", "Invoice 2", "Beta LLC", 900],
            [None, "Product C", None, None],
        ]
    )

    headered = df.iloc[1:].reset_index(drop=True)
    headered.columns = df.iloc[0].tolist()

    assert is_sales_register_parent_child(headered) is True


def test_sales_register_parent_child_is_flattened_before_normalization():
    raw = pd.DataFrame(
        [
            ["Date", "Particulars", "Buyer", "Buyer Address", "Export Sales"],
            ["2024-01-01", "INV-001", "Acme LLC", "Mumbai", 1200],
            [None, "Product A", None, None, None],
            [None, "Product B", None, None, None],
            ["2024-01-02", "INV-002", "Beta LLC", "Delhi", 900],
            [None, "Product C", None, None, None],
        ],
        columns=["Unnamed: 0", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3", "Unnamed: 4"],
    )

    structured = structure_dataframe(raw)

    assert list(structured["product"]) == ["Product A", "Product B", "Product C"]
    assert list(structured["customer"]) == ["Acme LLC", "Acme LLC", "Beta LLC"]
    assert list(structured["company"]) == ["INV-001", "INV-001", "INV-002"]
    assert len(structured) == 3


def test_plain_tabular_file_is_not_flattened():
    raw = pd.DataFrame(
        [
            ["Region", "Revenue", "Profit"],
            ["North", 100, 20],
            ["South", 150, 30],
        ],
        columns=["Unnamed: 0", "Unnamed: 1", "Unnamed: 2"],
    )

    structured = structure_dataframe(raw)

    assert list(structured.columns) == ["region", "revenue", "profit"]
    assert len(structured) == 2


def test_direct_flatten_sales_register_parent_child():
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01", None, None],
            "Particulars": ["INV-001", "Product A", "Product B"],
            "Buyer": ["Acme LLC", None, None],
            "Amount": [1000, None, None],
        }
    )

    flattened = flatten_sales_register_parent_child(df)

    assert list(flattened["Product"]) == ["Product A", "Product B"]
    assert flattened.loc[0, "Buyer"] == "Acme LLC"
