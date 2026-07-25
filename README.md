# CortexDB

A natural-language data analyst that reasons over SQL, not just translates it.

## What this is

Most "text-to-SQL" tools do one thing: turn a question into a single
query and return a table. CortexDB goes further. Ask it a lookup
question ("what were total sales by region?") and it behaves like a
normal text-to-SQL tool. But ask it an investigative question ("why
did profit drop in Q3?") and it behaves like an analyst — it forms a
plan, runs multiple queries to isolate the anomaly, checks for
confounding factors, and synthesizes a written explanation instead of
just handing back a number.

The goal is to demonstrate multi-step reasoning over structured data,
not just prompt-to-query translation.

## How it works

1. A user asks a question in plain English.
2. A planner decides whether this is a simple lookup or a deeper
   investigation.
3. **Simple lookups** go straight to SQL generation and execution.
4. **Investigations** are broken into steps: isolate the relevant
   time window/segment, slice by dimensions (region, category,
   product, etc.), check for statistical anomalies, rule out obvious
   confounders (discounts, seasonality, known events), and only then
   generate a final explanation.
5. Every generated query and its result is logged for auditability —
   you can always see exactly what the system ran and why.

## Tech stack

- **DuckDB** — embedded analytical SQL engine, no server required.
  Runs directly against the dataset with full SQL support (joins,
  window functions, CTEs).
- **LangGraph** — orchestrates the multi-step reasoning as a state
  graph, rather than a single linear prompt.
- **Groq API** — fast, free-tier LLM inference (Llama models) powering
  the natural-language understanding and SQL generation.
- **Python** — pandas/numpy for data handling, statsmodels for
  statistical anomaly detection (z-score, IQR, STL decomposition).
- **Postgres / SQLite** — stores the audit trail of every query run.

## Dataset

Uses the Superstore retail dataset (orders, customers, products,
sales, discounts, profit across 2014–2017) as the analytical target.
Any tabular dataset with a time dimension and a few categorical
dimensions (region, category, product, etc.) can be swapped in.

## Project structure

```
cortexdb/
  data/            raw dataset
  db/              DuckDB database file + loading script
  agent/           NL-to-SQL and reasoning agent logic
  requirements.txt
  .env.example
```

## Status

Early-stage / actively being built. Currently supports direct
NL-to-SQL querying against the dataset; multi-agent investigation
pipeline and audit logging are in progress.

## Setup

1. Clone the repo and create a virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add a free Groq API key from
   https://console.groq.com
4. Load the dataset: `python db/load_duckdb.py`
5. Ask a question: `python agent/nl_to_sql.py "your question here"`

## Why this project exists

Built to explore how far LLM-driven reasoning can go when it's given
structure — a real database, real statistics, and a disciplined
multi-step process — instead of just one prompt trying to do
everything at once.
