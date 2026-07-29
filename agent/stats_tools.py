"""
stats_tools.py

Statistical anomaly detection over a time series.

Primary method: STL decomposition (Seasonal-Trend decomposition using
LOESS). This separates the series into trend + seasonality + residual,
so a normal seasonal dip (e.g. every January being slow) does NOT get
flagged as an anomaly - only genuine deviations from the expected
seasonal pattern do.

Falls back to a simple rolling z-score if there isn't enough history
for STL (needs at least ~2 full seasonal cycles).
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import STL


def build_weekly_series(metric: str) -> pd.DataFrame:
    from agent.db_tools import run_sql
    ts = run_sql(f"""
        SELECT date_trunc('week', order_date) AS week, SUM({metric}) AS value
        FROM sales
        GROUP BY 1
        ORDER BY 1
    """)
    return ts


def _rolling_zscore_fallback(ts: pd.DataFrame, window: int = 8) -> dict:
    ts = ts.copy()
    ts["rolling_mean"] = ts["value"].rolling(window=window, min_periods=4).mean()
    ts["rolling_std"] = ts["value"].rolling(window=window, min_periods=4).std()
    ts["z_score"] = (ts["value"] - ts["rolling_mean"]) / ts["rolling_std"]

    valid = ts.dropna(subset=["z_score"])
    if valid.empty:
        return {}

    worst = valid.loc[valid["z_score"].idxmin()]
    return {
        "week_start": str(worst["week"].date()),
        "value": float(worst["value"]),
        "expected_value": float(worst["rolling_mean"]),
        "z_score": float(worst["z_score"]),
        "pct_drop": float((worst["value"] - worst["rolling_mean"]) / worst["rolling_mean"] * 100),
        "method": "rolling_zscore",
    }


def detect_worst_anomaly(ts: pd.DataFrame, period: int = 52) -> dict:
    """
    Flags the week with the most negative residual z-score after
    removing trend and seasonality via STL. This is the metric-drop
    detector for "why did X drop" style questions.
    """
    if len(ts) < period * 2:
        # not enough history for a reliable seasonal decomposition
        return _rolling_zscore_fallback(ts)

    series = ts.set_index("week")["value"]

    try:
        stl = STL(series, period=period, robust=True)
        result = stl.fit()
    except Exception:
        return _rolling_zscore_fallback(ts)

    residual = result.resid
    z = (residual - residual.mean()) / residual.std()

    worst_idx = z.idxmin()
    worst_z = float(z.loc[worst_idx])
    expected = float(result.trend.loc[worst_idx] + result.seasonal.loc[worst_idx])
    actual = float(series.loc[worst_idx])
    pct_drop = float((actual - expected) / expected * 100) if expected else 0.0

    return {
        "week_start": str(worst_idx.date()),
        "value": actual,
        "expected_value": expected,
        "z_score": worst_z,
        "pct_drop": pct_drop,
        "method": "stl_residual",
    }