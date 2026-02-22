"""
Revenue Engine — Single Source of Truth
========================================
All revenue aggregation, period comparison, and monthly normalization
MUST flow through this module.

# DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Tuple

from app.utils.file_processing import detect_currency, format_currency

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Column Detection Helpers
# ─────────────────────────────────────────────────────────────────────────────

_ID_PATTERNS = [
    'id', 'no', 'code', 'key', 'index', 'uuid', 'guid',
    'invoiceno', 'stockcode', 'customerid', 'orderid', 'transactionid'
]

def _is_id_col(col: str) -> bool:
    cleaned = col.lower().replace('_', '').replace(' ', '').replace('-', '')
    return any(p in cleaned for p in _ID_PATTERNS)


def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Return the best date column."""
    for col in df.columns:
        if any(kw in col.lower() for kw in ['date', 'time', 'day', 'month', 'year', 'period']):
            return col
    for col in df.select_dtypes(include=['object']).columns:
        try:
            pd.to_datetime(df[col].dropna().head(5))
            return col
        except Exception:
            continue
    return None


def detect_revenue_column(df: pd.DataFrame) -> Optional[str]:
    """
    Return the best revenue column.
    Priority: explicit revenue keywords > computed Revenue column > any numeric.
    """
    # Computed Revenue already present?
    if 'Revenue' in df.columns:
        return 'Revenue'

    numeric_cols = [c for c in df.select_dtypes(include=['number']).columns if not _is_id_col(c)]
    qty_kw = ['quantity', 'qty', 'units', 'unit', 'count', 'items']

    for col in numeric_cols:
        cl = col.lower()
        if any(k in cl for k in ['revenue', 'sales', 'amount', 'total', 'income', 'turnover']):
            return col
    for col in numeric_cols:
        cl = col.lower()
        if any(k in cl for k in ['profit', 'margin', 'net', 'earning']):
            return col
    # fallback: first numeric that isn't quantity-like
    for col in numeric_cols:
        if not any(k in col.lower() for k in qty_kw):
            return col
    return numeric_cols[0] if numeric_cols else None


def _try_compute_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """
    If df lacks a revenue column but has Quantity + UnitPrice, compute Revenue.
    Returns a copy — never mutates df.
    """
    def _find(patterns):
        for col in df.columns:
            cleaned = col.lower().replace('_', '').replace(' ', '')
            for p in patterns:
                if cleaned == p.replace('_', ''):
                    return col
        return None

    qty = _find(['quantity', 'qty', 'unitssold'])
    price = _find(['unitprice', 'unitprice', 'price'])
    if qty and price and 'Revenue' not in df.columns:
        df = df.copy()
        df['Revenue'] = (
            pd.to_numeric(df[qty], errors='coerce').fillna(0) *
            pd.to_numeric(df[price], errors='coerce').fillna(0)
        )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Core Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_monthly_revenue(
    df: pd.DataFrame,
    date_col: str,
    revenue_col: str,
    currency: Optional[str] = None,
) -> Dict:
    """
    Single source of truth for all revenue aggregation.

    Steps:
      A) Data Sanitisation — parse, coerce, drop nulls, sort
      B) Monthly Normalisation via resample("MS")
      C) Period Comparison (MoM)

    Returns a structured dict:
    {
        "monthly_series": [{"period": "YYYY-MM", "value": float}, ...],
        "current_period":  "YYYY-MM",
        "previous_period": "YYYY-MM",
        "current_value":   float,
        "previous_value":  float,
        "change_percent":  float,          # precise to 4dp
        "currency":        str,
        "n_months":        int,
        "integrity": {
            "rows_original":     int,
            "rows_after_clean":  int,
            "date_drop_pct":     float,
            "revenue_drop_pct":  float,
            "cv":                float,
        },
        "status": "ok" | "insufficient_data" | "invalid"
    }
    """
    # ── A) Sanitisation ──────────────────────────────────────────────────────
    df = df.copy()
    rows_original = len(df)

    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df[revenue_col] = pd.to_numeric(df[revenue_col], errors='coerce')

    rows_before_rev_drop = df[date_col].notna().sum()
    df = df.dropna(subset=[date_col, revenue_col])
    rows_after_clean = len(df)

    date_drop_pct = round((rows_original - rows_before_rev_drop) / max(rows_original, 1) * 100, 2)
    revenue_drop_pct = round((rows_before_rev_drop - rows_after_clean) / max(rows_before_rev_drop, 1) * 100, 2)

    df = df.sort_values(date_col)
    df = df.set_index(date_col)

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    # ── B) Monthly Normalisation ──────────────────────────────────────────────
    # Executive standard: always resample to "MS" (Month Start)
    monthly: pd.Series = df[revenue_col].resample("MS").sum()

    n_months = len(monthly)
    mean_rev = float(monthly.mean()) if n_months > 0 else 0.0
    std_rev = float(monthly.std()) if n_months > 1 else 0.0
    cv = std_rev / abs(mean_rev) if abs(mean_rev) > 0 else 10.0

    monthly_list = [
        {"period": str(idx.date())[:7], "value": float(val)}
        for idx, val in monthly.items()
    ]

    integrity = {
        "rows_original": rows_original,
        "rows_after_clean": rows_after_clean,
        "date_drop_pct": date_drop_pct,
        "revenue_drop_pct": revenue_drop_pct,
        "cv": round(cv, 4),
    }

    # ── C) Period Comparison ─────────────────────────────────────────────────
    if n_months < 2:
        return {
            "monthly_series": monthly_list,
            "current_period": monthly_list[-1]["period"] if monthly_list else None,
            "previous_period": None,
            "current_value": monthly_list[-1]["value"] if monthly_list else 0.0,
            "previous_value": None,
            "change_percent": None,
            "currency": currency or detect_currency(df.reset_index()),
            "n_months": n_months,
            "integrity": integrity,
            "status": "insufficient_data",
        }

    current_val = float(monthly.iloc[-1])
    previous_val = float(monthly.iloc[-2])
    current_period = str(monthly.index[-1].date())[:7]
    previous_period = str(monthly.index[-2].date())[:7]

    change_pct = round(
        ((current_val - previous_val) / abs(previous_val)) * 100, 4
    ) if previous_val != 0 else 0.0

    return {
        "monthly_series": monthly_list,
        "current_period": current_period,
        "previous_period": previous_period,
        "current_value": current_val,
        "previous_value": previous_val,
        "change_percent": change_pct,
        "currency": currency or detect_currency(df.reset_index()),
        "n_months": n_months,
        "integrity": integrity,
        "status": "ok",
    }


def get_monthly_series_from_result(revenue_result: Dict) -> pd.Series:
    """
    Reconstruct a DatetimeIndex pd.Series from compute_monthly_revenue output.
    Forecast must use this — never pass a raw dataframe.
    """
    data = revenue_result.get("monthly_series", [])
    if not data:
        return pd.Series(dtype=float)
    index = pd.to_datetime([item["period"] for item in data])
    values = [item["value"] for item in data]
    return pd.Series(values, index=index)


def compute_integrity_score(revenue_result: Dict, df: pd.DataFrame, revenue_col: str) -> Tuple[int, str]:
    """
    Data-driven integrity score (0–100).
    Replaces arbitrary "95% Excellent".

    Penalties:
      -10  Insufficient data (<2 months)
      -10  High volatility (CV > 1.2)
      -5   Revenue missing > 5%
      -5   Date parsing dropped > 2%
      -5   Fewer than 6 months of data
    """
    score = 100
    reasons = []

    integrity = revenue_result.get("integrity", {})
    status = revenue_result.get("status", "ok")
    n_months = revenue_result.get("n_months", 0)
    cv = integrity.get("cv", 0.0)
    revenue_drop_pct = integrity.get("revenue_drop_pct", 0.0)
    date_drop_pct = integrity.get("date_drop_pct", 0.0)

    if status == "insufficient_data" or n_months < 2:
        score -= 10
        reasons.append("Insufficient time-series data")

    if cv > 1.2:
        score -= 10
        reasons.append(f"High revenue volatility (CV={cv:.2f})")

    if revenue_drop_pct > 5:
        score -= 5
        reasons.append(f"Revenue column has >{revenue_drop_pct:.1f}% missing values")

    if date_drop_pct > 2:
        score -= 5
        reasons.append(f"Date parsing dropped {date_drop_pct:.1f}% of rows")

    if n_months < 6:
        score -= 5
        reasons.append(f"Only {n_months} months of history available")

    score = max(0, min(100, score))

    if score >= 80:
        quality = "Excellent"
    elif score >= 65:
        quality = "Good"
    elif score >= 45:
        quality = "Fair"
    else:
        quality = "Poor"

    return score, quality, reasons


def compute_volatility(monthly_series: pd.Series) -> Dict:
    """
    Compute Coefficient of Variation (CV) to determine Revenue Stability Index.
    """
    if len(monthly_series) < 2:
        return {"cv": 0.0, "stability_label": "Insufficient Data"}

    mean = monthly_series.mean()
    std = monthly_series.std()
    
    cv = float(std / mean) if abs(mean) > 0 else 0.0

    if cv < 0.10:
        stability = "High Stability"
    elif cv < 0.25:
        stability = "Moderate Stability"
    else:
        stability = "High Volatility"

    return {
        "cv": round(cv, 4),
        "stability_label": stability
    }
