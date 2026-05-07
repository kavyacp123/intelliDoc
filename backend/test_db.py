import sqlite3
import duckdb
from app.core.database import get_connection

conn = get_connection()
row = conn.execute("SELECT dataset_id, table_name FROM datasets ORDER BY rowid DESC LIMIT 1").fetchone()
if row:
    print(f"Dataset ID: {row[0]}, Table: {row[1]}")
    res = conn.execute(f'SELECT * FROM "{row[1]}" LIMIT 5').fetchall()
    print("First 5 rows:", res)
else:
    print("No datasets.")
