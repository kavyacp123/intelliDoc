"""
Strategy:
---------
The original Excel has a "parent-child" layout:
  - PARENT ROW: has a Date + company info in col 0 → this is a sale transaction
  - CHILD ROW(S): only col 1 has a product name, all other cols are NaN → products sold in that transaction

Goal: For each product row, copy the parent transaction details into the same row.
Result: One flat row per (transaction × product).
"""

import pandas as pd
import re

INPUT_FILE = "1777013291165_SR_22-23.xls"
OUTPUT_FILE = "flattened_sales_register.xlsx"

# ── 1. Load raw sheet (no header) ──────────────────────────────────────────
df_raw = pd.read_excel(INPUT_FILE, sheet_name=0, header=None)

# ── 2. Find the actual header row (the one that says "Date", "Particulars", …)
header_row_idx = None
for i, row in df_raw.iterrows():
    if str(row.iloc[0]).strip() == "Date":
        header_row_idx = i
        break

if header_row_idx is None:
    raise ValueError("Could not find header row with 'Date' in column 0")

columns = df_raw.iloc[header_row_idx].tolist()
data_start = header_row_idx + 1

# ── 3. Work only with data rows ─────────────────────────────────────────────
df_data = df_raw.iloc[data_start:].reset_index(drop=True)
df_data.columns = columns

# ── 4. Detect "parent" vs "child" rows ──────────────────────────────────────
# Parent row  → col 0 (Date) is a real datetime/date value
# Child row   → col 0 is NaT/NaN, only col 1 (Particulars = product name) has a value
def is_parent(row):
    return pd.notna(row["Date"]) and str(row["Date"]).strip() not in ("", "nan", "NaT")

def is_product_child(row):
    """True when only 'Particulars' carries data (= product name row)."""
    date_empty = pd.isna(row["Date"])
    particulars_filled = pd.notna(row["Particulars"]) and str(row["Particulars"]).strip() != ""
    # All other columns are NaN
    other_cols = [c for c in df_data.columns if c not in ("Date", "Particulars")]
    all_others_empty = all(pd.isna(row[c]) for c in other_cols)
    return date_empty and particulars_filled and all_others_empty

# ── 5. Build flat table ──────────────────────────────────────────────────────
flat_rows = []
current_parent = None

for _, row in df_data.iterrows():
    row_dict = row.to_dict()

    # Skip completely empty rows or summary/footer rows
    if pd.isna(row["Date"]) and (pd.isna(row["Particulars"]) or str(row["Particulars"]).strip() == ""):
        continue

    if is_parent(row):
        current_parent = row_dict.copy()
        # Don't emit yet — wait for at least one product row

    elif is_product_child(row) and current_parent is not None:
        # Merge: take all parent fields, replace 'Particulars' with product name
        merged = current_parent.copy()
        merged["Product"] = str(row["Particulars"]).strip()
        flat_rows.append(merged)

    else:
        # Rows that have Date AND extra data (e.g. multi-product parent with values already)
        # Treat as a standalone row with Particulars as the product
        if current_parent is not None and pd.notna(row.get("Particulars")):
            merged = row_dict.copy()
            merged["Product"] = str(row["Particulars"]).strip()
            flat_rows.append(merged)

# ── 6. Build output DataFrame ────────────────────────────────────────────────
df_flat = pd.DataFrame(flat_rows)

# Re-order: Date, Product, then all other columns (drop original 'Particulars' – replaced by 'Product')
priority_cols = ["Date", "Product"]
other_cols = [c for c in df_flat.columns if c not in priority_cols + ["Particulars"]]
df_flat = df_flat[priority_cols + other_cols]

# Rename for clarity
df_flat.rename(columns={
    "Buyer": "Buyer Name",
    "Buyer Address": "Buyer Address",
}, inplace=True)

# Clean up Date column
df_flat["Date"] = pd.to_datetime(df_flat["Date"], errors="coerce").dt.date

# Drop rows where both Date and Product are empty
df_flat = df_flat[df_flat["Product"].notna() & (df_flat["Product"] != "")]

df_flat.reset_index(drop=True, inplace=True)

# ── 7. Write to Excel ────────────────────────────────────────────────────────
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

wb = Workbook()
ws = wb.active
ws.title = "Flat Sales Register"

header_fill = PatternFill("solid", start_color="1F4E79", end_color="1F4E79")
header_font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
data_font   = Font(name="Arial", size=9)
alt_fill    = PatternFill("solid", start_color="EBF3FB", end_color="EBF3FB")

for r_idx, row in enumerate(dataframe_to_rows(df_flat, index=False, header=True), start=1):
    ws.append(row)
    for cell in ws[r_idx]:
        if r_idx == 1:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        else:
            cell.font = data_font
            if r_idx % 2 == 0:
                cell.fill = alt_fill

# Auto-fit column widths (capped at 50)
for col in ws.columns:
    max_len = max((len(str(c.value)) if c.value else 0) for c in col)
    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

ws.freeze_panes = "A2"

wb.save(OUTPUT_FILE)
print(f"✅ Done! {len(df_flat)} flat rows written to '{OUTPUT_FILE}'")
print(f"   Columns: {list(df_flat.columns)}")
