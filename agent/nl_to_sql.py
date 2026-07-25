"""
nl_to_sql.py

Phase 1 baseline: takes ONE natural-language question, asks an LLM
(via Groq's free API) to write a DuckDB SQL query against the `sales`
table, runs it, and prints the result.

No agents, no LangGraph yet - this is the "hands" the planner /
investigator / statistician / narrator agents will call in phase 2.

Run from the repo root:
    python agent/nl_to_sql.py "What were total sales by region?"
"""

import os
import sys
import duckdb
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

SCHEMA = """
Table: sales
Columns:
  row_id         INTEGER   -- row identifier
  order_id       VARCHAR   -- order identifier, repeats across line items
  order_date     TIMESTAMP      -- date the order was placed
  ship_date      TIMESTAMP      -- date the order shipped
  ship_mode      VARCHAR   -- e.g. Standard Class, Second Class, First Class, Same Day
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
  sales          DOUBLE    -- revenue for the line item
  quantity       INTEGER   -- units sold
  discount       DOUBLE    -- discount fraction, e.g. 0.2 = 20%
  profit         DOUBLE    -- profit for the line item, can be negative
"""

SYSTEM_PROMPT = f"""You are a SQL generator for DuckDB.
Given the schema below, write ONE valid DuckDB SQL query that answers
the user's question. Return ONLY the SQL - no explanation, no markdown
fences, no preamble.

{SCHEMA}
"""


def nl_to_sql(question: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    sql = response.choices[0].message.content.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def run_query(sql: str):
    con = duckdb.connect("db/cortex.duckdb")
    result_df = con.execute(sql).fetchdf()
    con.close()
    return result_df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python agent/nl_to_sql.py "your question here"')
        sys.exit(1)

    question = sys.argv[1]
    print(f"\nQuestion: {question}\n")

    sql = nl_to_sql(question)
    print(f"Generated SQL:\n{sql}\n")

    try:
        df = run_query(sql)
        print("Result:")
        print(df.to_string(index=False))
    except Exception as e:
        print(f"Query failed: {e}")