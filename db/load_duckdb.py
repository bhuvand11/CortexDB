"""
load_duckdb.py

Loads the real Superstore CSV into a persisted DuckDB database file
(db/cortex.duckdb), renaming columns to clean snake_case along the way.

Kaggle's Superstore CSV is typically saved in Windows-1252 (cp1252)
encoding, not UTF-8, so we let pandas read it (it handles cp1252
cleanly) and then hand DuckDB a ready-made DataFrame instead of
asking DuckDB's CSV reader to guess the encoding.

Run from the repo root:
    python db/load_duckdb.py
"""

import os
import duckdb
import pandas as pd

os.makedirs("db", exist_ok=True)

try:
    df = pd.read_csv("data/sales.csv", encoding="utf-8")
except UnicodeDecodeError:
    print("UTF-8 failed, retrying with cp1252 (Windows-1252)...")
    df = pd.read_csv("data/sales.csv", encoding="cp1252")

df = df.rename(columns={
    "Row ID": "row_id",
    "Order ID": "order_id",
    "Order Date": "order_date",
    "Ship Date": "ship_date",
    "Ship Mode": "ship_mode",
    "Customer ID": "customer_id",
    "Customer Name": "customer_name",
    "Segment": "segment",
    "Country": "country",
    "City": "city",
    "State": "state",
    "Postal Code": "postal_code",
    "Region": "region",
    "Product ID": "product_id",
    "Category": "category",
    "Sub-Category": "sub_category",
    "Product Name": "product_name",
    "Sales": "sales",
    "Quantity": "quantity",
    "Discount": "discount",
    "Profit": "profit",
})

df["order_date"] = pd.to_datetime(df["order_date"], format="%m/%d/%Y")
df["ship_date"] = pd.to_datetime(df["ship_date"], format="%m/%d/%Y")

con = duckdb.connect("db/cortex.duckdb")
con.execute("CREATE OR REPLACE TABLE sales AS SELECT * FROM df")

row_count = con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
print(f"Loaded {row_count:,} rows into db/cortex.duckdb -> table 'sales'")

print("\nSchema:")
print(con.execute("DESCRIBE sales").fetchdf())

print("\nDate range:")
print(con.execute("SELECT MIN(order_date), MAX(order_date) FROM sales").fetchdf())

print("\nSample rows:")
print(con.execute(
    "SELECT order_date, region, category, sub_category, sales, profit FROM sales LIMIT 5"
).fetchdf())

con.close()