import pandas as pd
try:
    df = pd.read_excel("../Financial Sample.xlsx", engine="openpyxl")
    print(df.head())
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
