"""
db_tools.py

DuckDB connection helper used by every node.
"""

import duckdb
import pandas as pd

DB_PATH = "db/cortex.duckdb"

SCHEMA = """
Table: sales
Columns:
  row_id         INTEGER
  order_id       VARCHAR
  order_date     TIMESTAMP
  ship_date      TIMESTAMP
  ship_mode      VARCHAR
  customer_id    VARCHAR
  customer_name  VARCHAR
  segment        VARCHAR   -- Consumer, Corporate, Home Office
  country        VARCHAR
  city           VARCHAR
  state          VARCHAR
  postal_code    VARCHAR
  region         VARCHAR   -- East, West, Central, South
  product_id     VARCHAR
  category       VARCHAR   -- Furniture, Office Supplies, Technology
  sub_category   VARCHAR   -- e.g. Chairs, Binders, Phones, Storage
  product_name   VARCHAR
  sales          DOUBLE
  quantity       INTEGER
  discount       DOUBLE
  profit         DOUBLE
"""


def run_sql(sql: str) -> pd.DataFrame:
    con = duckdb.connect(DB_PATH)
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()