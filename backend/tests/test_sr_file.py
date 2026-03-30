import os
import sys

# Setup paths
workspace_dir = "/Users/kavyapatel/Desktop/final inteldoc "
backend_dir = os.path.join(workspace_dir, "intelliDoc", "backend")
sys.path.insert(0, backend_dir)

from app.services.file_service import _parse_file

def test_sr_file():
    file_path = os.path.join(workspace_dir, "SR_22-23.xls")
    print(f"Loading {file_path}...")
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    print("Testing the parsing pipeline...")
    
    # We use _parse_file which now also executes clean_dataframe natively inside if we want...
    # Wait, _parse_file just parses it into a df. Let's look at process_upload's logic
    from app.utils.parser_utils import clean_dataframe
    import pandas as pd
    
    # Simulate step 1: 
    print("Reading Excel...")
    try:
        from io import BytesIO
        # Since the extension is .xls, we'll try to let Pandas decide the engine instead of forcing openpyxl
        sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
        best_sheet = None
        max_len = -1
        for name, sheet_df in sheets.items():
            if len(sheet_df) > max_len:
                max_len = len(sheet_df)
                best_sheet = sheet_df
        df = best_sheet if best_sheet is not None else pd.DataFrame()
        print(f"Raw shape: {df.shape}")
        
    except Exception as e:
        print(f"Exception during parse: {e}")
        return
        
    print("\nCleaning DataFrame...")
    clean_df = clean_dataframe(df)
    
    print(f"Clean shape: {clean_df.shape}")
    print("\nColumns:")
    print(clean_df.columns.tolist())
    
    print("\n--- Searching for Qualifine Chemical LLC ---")
    
    # Search for variations of "qualifine" in buyer or particulars
    # Convert to lowercase for case-insensitive match
    mask = clean_df['buyer'].str.lower().str.contains('qualifine', na=False) | \
           clean_df['particulars'].str.lower().str.contains('qualifine', na=False)
           
    results = clean_df[mask]
    
    if len(results) > 0:
        print(f"Found {len(results)} matches!")
        for idx, row in results.iterrows():
            print(f"\nMatch Index in Cleaned DF: {idx}")
            print(f"Buyer: {row['buyer']}")
            print(f"Particulars: {row['particulars']}")
            print(f"Export Sales: {row.get('export_sales', 'Column Not Found')}")
            print(f"Packing Charges: {row.get('packing_charges', 'Column Not Found')}")
    else:
        print("Could not find 'Qualifine Chemical LLC' in the cleaned dataframe.")

if __name__ == "__main__":
    test_sr_file()
