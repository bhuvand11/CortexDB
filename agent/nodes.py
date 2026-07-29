"""
nodes.py

Every node in the CortexDB reasoning graph.
"""

import json
import pandas as pd
from agent.state import CortexState
from agent.llm import ask_llm
from agent.db_tools import run_sql, SCHEMA
from agent.stats_tools import build_weekly_series, detect_worst_anomaly
from agent.audit import log_step


# ---------------------------------------------------------------- planner
def planner_node(state: CortexState) -> dict:
    question = state["question"]

    system = f"""You classify data-analyst questions into one of two routes.

"lookup" = the question asks for a direct fact/aggregate (totals, top N, averages).
"investigate" = the question asks WHY something happened, or about a
change/drop/spike/anomaly over time.

Also identify which metric the question is about: "sales" or "profit".
If unclear, default to "sales".

Respond with ONLY valid JSON, no markdown, in this exact shape:
{{"route": "lookup" or "investigate", "metric": "sales" or "profit"}}
"""

    raw = ask_llm(system, question)
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
        route = parsed.get("route", "lookup")
        metric = parsed.get("metric", "sales")
    except Exception:
        route, metric = "lookup", "sales"

    log_step(question, "planner", summary=f"route={route}, metric={metric}")
    return {"route": route, "metric": metric}


def route_decision(state: CortexState) -> str:
    return state.get("route", "lookup")


# ------------------------------------------------------------- sql agent
def sql_agent_node(state: CortexState) -> dict:
    question = state["question"]

    system = f"""You are a SQL generator for DuckDB.
Given the schema below, write ONE valid DuckDB SQL query that answers
the user's question. Return ONLY the SQL - no explanation, no markdown.

{SCHEMA}
"""
    sql = ask_llm(system, question)
    sql = sql.replace("```sql", "").replace("```", "").strip()

    try:
        df = run_sql(sql)
        result_str = df.to_string(index=False)
    except Exception as e:
        result_str = f"Query failed: {e}"

    log_step(question, "sql_agent", sql_text=sql, summary=result_str[:300])

    answer = f"SQL used:\n{sql}\n\nResult:\n{result_str}"
    return {"lookup_sql": sql, "lookup_result": result_str, "final_answer": answer}


# ---------------------------------------------------------- investigator
def investigator_node(state: CortexState) -> dict:
    metric = state.get("metric", "sales")
    ts = build_weekly_series(metric)
    anomaly = detect_worst_anomaly(ts)

    log_step(
        state["question"], "investigator",
        summary=f"weekly series built ({len(ts)} weeks), worst anomaly: {anomaly}"
    )
    return {"anomaly": anomaly}


# --------------------------------------------------------------- segment
def segment_node(state: CortexState) -> dict:
    metric = state.get("metric", "sales")
    anomaly = state.get("anomaly", {})

    if not anomaly:
        return {"worst_segment": {}}

    window_start = anomaly["week_start"]
    window_end = (pd.Timestamp(window_start) + pd.Timedelta(days=7)).date().isoformat()
    baseline_start = (pd.Timestamp(window_start) - pd.Timedelta(weeks=8)).date().isoformat()
    baseline_end = window_start

    anomaly_seg = run_sql(f"""
        SELECT region, sub_category, SUM({metric}) AS value, COUNT(*) AS orders
        FROM sales
        WHERE order_date >= '{window_start}' AND order_date < '{window_end}'
        GROUP BY region, sub_category
    """)
    baseline_seg = run_sql(f"""
        SELECT region, sub_category, SUM({metric}) / 8.0 AS baseline_value, COUNT(*) AS baseline_orders
        FROM sales
        WHERE order_date >= '{baseline_start}' AND order_date < '{baseline_end}'
        GROUP BY region, sub_category
    """)

    merged = baseline_seg.merge(anomaly_seg, on=["region", "sub_category"], how="left").fillna(0)
    merged["delta"] = merged["value"] - merged["baseline_value"]

    if merged.empty:
        return {"worst_segment": {}}

    # Total company-wide drop, from the investigator's overall series -
    # this is the number we need any segment-level story to actually explain.
    total_drop = anomaly["value"] - anomaly["expected_value"]

    MIN_BASELINE_ORDERS = 5
    reliable = merged[merged["baseline_orders"] >= MIN_BASELINE_ORDERS]
    candidates = reliable if not reliable.empty else merged

    worst = candidates.loc[candidates["delta"].idxmin()]

    # How much of the total drop does this one segment actually explain?
    pct_of_total_drop = (worst["delta"] / total_drop * 100) if total_drop else 0.0

    # Is the drop concentrated in a few segments, or spread thin across
    # many (i.e. a broad, diffuse decline rather than one bad segment)?
    top5 = candidates.nsmallest(5, "delta")
    top5_pct_of_drop = (top5["delta"].sum() / total_drop * 100) if total_drop else 0.0
    is_concentrated = pct_of_total_drop >= 30  # one segment alone explains 30%+

    worst_segment = {
        "region": worst["region"],
        "sub_category": worst["sub_category"],
        "actual": float(worst["value"]),
        "expected": float(worst["baseline_value"]),
        "delta": float(worst["delta"]),
        "baseline_order_count": int(worst["baseline_orders"]),
        "window_start": window_start,
        "window_end": window_end,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "low_confidence": bool(worst["baseline_orders"] < MIN_BASELINE_ORDERS),
        "total_company_drop": float(total_drop),
        "pct_of_total_drop": float(pct_of_total_drop),
        "top5_pct_of_drop": float(top5_pct_of_drop),
        "is_concentrated": bool(is_concentrated),
    }

    log_step(state["question"], "segment", summary=str(worst_segment))
    return {"worst_segment": worst_segment}


# ----------------------------------------------------------- confounders
def confounder_node(state: CortexState) -> dict:
    seg = state.get("worst_segment", {})
    if not seg:
        return {"confounders": {}}

    def stats_for_window(start, end):
        df = run_sql(f"""
            SELECT COUNT(*) AS orders, AVG(discount) AS avg_discount, SUM(quantity) AS total_qty
            FROM sales
            WHERE region = '{seg['region']}' AND sub_category = '{seg['sub_category']}'
            AND order_date >= '{start}' AND order_date < '{end}'
        """)
        return df.iloc[0].to_dict()

    anomaly_stats = stats_for_window(seg["window_start"], seg["window_end"])
    baseline_stats = stats_for_window(seg["baseline_start"], seg["baseline_end"])

    confounders = {
        "anomaly_orders": anomaly_stats["orders"],
        "baseline_orders": baseline_stats["orders"],
        "anomaly_avg_discount": anomaly_stats["avg_discount"],
        "baseline_avg_discount": baseline_stats["avg_discount"],
        # We have no inventory/stock data in this dataset, so we can
        # only observe that zero orders were placed - NOT that an
        # item was actually out of stock. Keep the label honest.
        "zero_orders_in_window": anomaly_stats["orders"] == 0,
        "low_confidence": seg.get("low_confidence", False),
    }

    log_step(state["question"], "confounders", summary=str(confounders))
    return {"confounders": confounders}


# -------------------------------------------------------------- context
# A small set of known external events. Not exhaustive - this is meant
# to demonstrate that some "why" questions need context outside the
# transactional data itself, not to be a real events database.
KNOWN_EVENTS = [
    {"start": "2014-11-04", "end": "2014-11-04", "name": "2014 US midterm elections"},
    {"start": "2015-11-27", "end": "2015-11-28", "name": "Thanksgiving / Black Friday 2015"},
    {"start": "2016-11-08", "end": "2016-11-08", "name": "2016 US presidential election"},
    {"start": "2016-11-24", "end": "2016-11-25", "name": "Thanksgiving / Black Friday 2016"},
    {"start": "2017-01-20", "end": "2017-01-20", "name": "2017 US presidential inauguration"},
]


def context_node(state: CortexState) -> dict:
    anomaly = state.get("anomaly", {})
    week_start = anomaly.get("week_start")
    if not week_start:
        return {"context_events": []}

    window_end = str((pd.Timestamp(week_start) + pd.Timedelta(days=7)).date())
    # wider buffer - effects of a major event can trail into the
    # following 1-2 weeks, not just a few days
    buffered_start = str((pd.Timestamp(week_start) - pd.Timedelta(days=10)).date())

    matches = [
        e["name"] for e in KNOWN_EVENTS
        if not (e["end"] < buffered_start or e["start"] > window_end)
    ]

    log_step(state["question"], "context", summary=f"matched events: {matches}")
    return {"context_events": matches}


# --------------------------------------------------------------- narrator
def narrator_node(state: CortexState) -> dict:
    question = state["question"]
    anomaly = state.get("anomaly", {})
    seg = state.get("worst_segment", {})
    conf = state.get("confounders", {})
    context_events = state.get("context_events", [])

    confidence_note = (
        "NOTE: this segment had very few orders in the baseline period, "
        "so treat this finding as tentative, not conclusive."
        if conf.get("low_confidence") else ""
    )

    context_line = (
        f"Possible external context: this window overlaps with: {', '.join(context_events)}. "
        f"This is a plausible contributing factor, but not confirmed by the transaction data alone."
        if context_events else
        "No known external events overlap with this window."
    )

    findings = f"""
Anomaly detected: week of {anomaly.get('week_start')}, metric dropped to
{anomaly.get('value'):.2f} vs an expected {anomaly.get('expected_value'):.2f}
({anomaly.get('pct_drop'):.1f}% drop, z-score {anomaly.get('z_score'):.2f},
detected via {anomaly.get('method')}). Total company-wide drop: {seg.get('total_company_drop', 0):.2f}.

{context_line}

Single worst segment: {seg.get('region')} / {seg.get('sub_category')}.
This segment's drop was {seg.get('delta', 0):.2f}, which is {seg.get('pct_of_total_drop', 0):.1f}%
of the total company-wide drop.
The top 5 worst segments combined explain {seg.get('top5_pct_of_drop', 0):.1f}% of the total drop.
This decline is: {"CONCENTRATED in a few segments" if seg.get('is_concentrated') else "DIFFUSE - spread thinly across many segments, no single segment is really the cause"}.
Baseline order count for the worst segment: {seg.get('baseline_order_count')}.
{confidence_note}

Order count in anomaly window: {conf.get('anomaly_orders')} (baseline: {conf.get('baseline_orders')}).
Average discount in anomaly window: {conf.get('anomaly_avg_discount')} (baseline: {conf.get('baseline_avg_discount')}).
Zero orders were placed in this window: {conf.get('zero_orders_in_window')}.
"""

    system = """You are a senior data analyst writing a final explanation
for a business stakeholder. Given the investigation findings below,
write a clear, confident, 3-5 sentence explanation.

CRITICAL: only claim a specific segment "caused" or was the "primary
driver" of the drop if pct_of_total_drop is reasonably large (say 25%+).
If the decline is DIFFUSE, say so plainly - e.g. "the drop was broad-based
across many segments rather than caused by any single one" - and mention
the worst segment only as the single largest contributor, not as the cause.

If there is possible external context (a known event overlapping the
window), mention it as a PLAUSIBLE but UNCONFIRMED contributing factor -
never state it as a proven cause, since the transaction data alone
cannot confirm it.

This dataset has no inventory/stock-level data. If orders were zero,
describe it as "no orders were placed" - do NOT claim "stockout" or
imply an inventory cause. If low_confidence is true, say the finding
is tentative."""

    answer = ask_llm(system, f"Original question: {question}\n\nFindings:\n{findings}")

    log_step(question, "narrator", summary=answer[:300])
    return {"final_answer": answer, "findings": [findings]}