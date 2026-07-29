# CortexDB

A natural-language data analyst that reasons over SQL, not just translates it.

## What this is

Most "text-to-SQL" tools do one thing: turn a question into a single
query and return a table. CortexDB goes further. Ask it a lookup
question ("what were total sales by region?") and it behaves like a
normal text-to-SQL tool. But ask it an investigative question ("why
did sales drop unexpectedly?") and it behaves like an analyst — it
forms a plan, runs multiple queries to isolate the anomaly, checks
whether the cause is concentrated in one segment or spread across
many, rules out obvious confounders, checks for relevant external
context, and only then synthesizes a written explanation instead of
just handing back a number.

The goal is to demonstrate multi-step reasoning over structured data,
not just prompt-to-query translation — and to do it honestly: the
system is built to say "the cause isn't clear" or "this is only a
partial explanation" rather than confidently overclaiming.

## How it works

1. A user asks a question in plain English.
2. A **planner** agent classifies the question as a simple lookup or
   a deeper investigation, and identifies which metric it's about
   (sales or profit).
3. **Simple lookups** go straight to SQL generation and execution
   against the dataset.
4. **Investigations** run through a chain of agents:
   - **Investigator** — builds a weekly time series for the metric
     and runs STL (Seasonal-Trend decomposition) to find the most
     statistically significant anomaly, correctly ignoring normal
     seasonal patterns (e.g. a holiday-season dip isn't flagged as
     an anomaly, since it's expected).
   - **Segment** — breaks the anomaly window down by region and
     sub-category to find the worst-hit segment, but also checks
     whether that segment actually explains a meaningful share of
     the total drop — if the decline is spread thin across many
     segments, the system says so instead of pinning it on whichever
     segment happened to fall the most in raw dollars.
   - **Confounders** — checks order counts and discount levels in
     the anomaly window vs. a baseline period, and flags low-volume
     segments as low-confidence rather than treating a single
     lucky/unlucky order as a real pattern.
   - **Context** — checks whether the anomaly window overlaps with
     any known external events (e.g. elections, major holidays),
     surfacing them as a plausible but unconfirmed factor rather than
     a proven cause.
   - **Narrator** — synthesizes everything into a final written
     explanation, explicitly instructed not to overclaim a single
     cause when the evidence doesn't support one.
5. Every step — every SQL query, every agent's findings — is logged
   to a SQLite audit trail, so the full reasoning chain is inspectable
   after the fact. Nothing is a black box.

### Example: a real investigation from this project

Asking `"Why did sales drop unexpectedly?"` against the real Superstore
dataset, the system found a 58.1% week-over-week drop (detected via
STL, not just a naive threshold), determined the decline was diffuse
rather than caused by any single segment (the worst segment explained
only 5.7% of the total drop), and flagged that the anomaly window
overlapped with the 2016 US presidential election as a plausible,
unconfirmed contributing factor — instead of confidently blaming a
single product/region the way a naive system would.

## Tech stack

- **DuckDB** — embedded analytical SQL engine, no server required.
  Runs directly against the dataset with full SQL support (joins,
  window functions, CTEs, date truncation for time-series work).
- **LangGraph** — orchestrates the multi-step reasoning as a state
  graph with conditional routing (lookup vs. investigate), rather
  than a single linear prompt.
- **Groq API** — fast, free-tier LLM inference (Llama 3.3 70B) powering
  natural-language classification, SQL generation, and the final
  narrative synthesis.
- **Python** — pandas/numpy for data handling, **statsmodels** for
  statistical anomaly detection via STL (Seasonal-Trend decomposition
  using LOESS), which separates trend and seasonality from real
  anomalies.
- **SQLite** — stores the full audit trail (every node, every SQL
  query, every finding) for every question asked.

## Dataset

Uses the real Superstore retail dataset (orders, customers, products,
sales, discounts, profit across 2014–2017) as the analytical target —
not synthetic data, so every finding the system produces is a genuine
discovery, not a scripted answer. Any tabular dataset with a time
dimension and a few categorical dimensions (region, category, product,
etc.) can be swapped in by adjusting the schema in `agent/db_tools.py`.

## Project structure

```
cortexdb/
  data/
    sales.csv              # raw Superstore dataset
  db/
    load_duckdb.py          # loads the CSV into DuckDB
    cortex.duckdb            # generated, not committed
    audit.sqlite             # generated audit trail, not committed
  agent/
    __init__.py
    state.py                # shared state passed between graph nodes
    llm.py                  # Groq client wrapper
    db_tools.py              # DuckDB connection + schema
    stats_tools.py           # STL-based anomaly detection
    audit.py                 # SQLite audit logging
    nodes.py                 # planner, sql_agent, investigator, segment,
                              # confounders, context, narrator
    graph.py                 # LangGraph state machine wiring
    main.py                  # phase 2 entry point (full pipeline)
    nl_to_sql.py              # phase 1 baseline (direct NL-to-SQL, no agents)
  requirements.txt
  .env.example
```

## Status

Core pipeline complete: planner-routed lookup and investigation paths,
STL-based anomaly detection, segment analysis with confidence checks,
confounder analysis, external context matching, narrative synthesis,
and full SQLite audit logging. Currently CLI-based; a frontend and
additional robustness (e.g. letting users specify a time period
directly instead of only auto-detecting the worst anomaly) are
potential next steps.

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add a free Groq API key from
   https://console.groq.com
4. Load the dataset into DuckDB:
   ```bash
   python db/load_duckdb.py
   ```
5. Ask a question through the full reasoning pipeline:
   ```bash
   python -m agent.main "Why did sales drop unexpectedly?"
   python -m agent.main "What are total sales by region?"
   ```
6. (Optional) Use the phase 1 baseline for a single direct query
   without the multi-agent pipeline:
   ```bash
   python agent/nl_to_sql.py "your question here"
   ```
7. Inspect the full reasoning trace for any question:
   ```bash
   sqlite3 db/audit.sqlite "SELECT node_name, summary FROM audit_log"
   ```

## Why this project exists

Built to explore how far LLM-driven reasoning can go when it's given
structure — a real database, real statistics, and a disciplined
multi-step process — instead of just one prompt trying to do
everything at once. The harder problem isn't generating SQL; it's
building a system that knows the difference between a real cause and
a plausible-sounding one, and says so honestly.
