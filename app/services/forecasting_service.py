"""
Forecasting Service — consumes Revenue Engine output.

# DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
All time-series input comes from compute_monthly_revenue() or
get_monthly_series_from_result().
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, r2_score

from app.services.revenue_engine import (
    compute_monthly_revenue,
    get_monthly_series_from_result,
    detect_date_column,
    detect_revenue_column,
    _try_compute_revenue,
    compute_volatility,
)
from app.utils.file_processing import detect_currency

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public Entry Point (receives raw df — delegates aggregation to revenue engine)
# ─────────────────────────────────────────────────────────────────────────────

def generate_forecast(
    df: pd.DataFrame,
    revenue_column: str,
    date_column: str,
    periods: int = 3,
    rev_result: Optional[Dict] = None,
) -> Dict:
    """
    Enterprise-grade forecast.

    Flow:
      1. Compute revenue via revenue_engine (monthly normalisation)
      2. Extract pd.Series from result
      3. Apply gates (N, CV, R²)
      4. Fit SARIMAX → Holt-Winters fallback
      5. Return structured output

    # DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
    """
    currency = detect_currency(df)

    # ── Step 1: compute via Revenue Engine ────────────────────────────────────
    if rev_result is None:
        df = _try_compute_revenue(df)
        rev_result = compute_monthly_revenue(df, date_column, revenue_column, currency=currency)

    if rev_result["status"] == "insufficient_data":
        return _invalid_response(
            [], currency,
            "Forecast not reliable due to insufficient data points."
        )

    # ── Step 2: extract monthly series ────────────────────────────────────────
    ts: pd.Series = get_monthly_series_from_result(rev_result)
    if ts.empty:
        return _invalid_response([], currency, "No monthly revenue data found.")

    # Properly align index to Month Start and ensure frequency is set
    ts.index = pd.to_datetime(ts.index)
    ts = ts.asfreq("MS").fillna(0)

    n = len(ts)
    mean_rev = float(ts.mean())
    std_rev = float(ts.std())
    cv = std_rev / abs(mean_rev) if abs(mean_rev) > 0 else 10.0
    volatility = compute_volatility(ts)

    logger.info("Forecasting: Points=%d, CV=%.2f, Currency=%s", n, cv, currency)

    # ── Step 3: Reliability Gates ──────────────────────────────────────────────
    historical_list = [{"date": str(idx.date()), "value": float(val)} for idx, val in ts.items()]

    if n < 8: # Reduced from 12 to 8 to be more lenient for newer datasets
        return _invalid_response(historical_list, currency, "Forecast not reliable due to insufficient data points.")
    if cv > 2.0: # Increased from 1.2 to 2.0 to handle more volatile datasets
        return _invalid_response(historical_list, currency, "Forecast not reliable due to extreme volatility.")

    # ── Step 4: Hierarchical Model Selection ──────────────────────────────────
    model_used = "none"
    metric_r2 = -1.0
    metric_mae = 0.0
    metric_mape = 0.0
    forecast_values = []
    conf_int_lower = []
    conf_int_upper = []

    s = 12  # monthly data always has seasonality period 12

    if n >= 18:
        try:
            model = SARIMAX(ts, order=(1, 1, 1), seasonal_order=(1, 1, 1, s),
                            enforce_stationarity=False, enforce_invertibility=False)
            results = model.fit(disp=False)
            y_pred = results.fittedvalues.fillna(0)
            
            # Ensure no NaNs or Infs in y_pred before R2
            if not np.any(np.isnan(y_pred)) and not np.any(np.isinf(y_pred)):
                metric_r2 = r2_score(ts, y_pred)

                if metric_r2 >= 0:
                    model_used = "sarimax"
                    f_res = results.get_forecast(steps=periods)
                    forecast_values = f_res.predicted_mean.fillna(0)
                    ci = f_res.conf_int().fillna(0)
                    conf_int_lower = ci.iloc[:, 0].tolist()
                    conf_int_upper = ci.iloc[:, 1].tolist()
                    metric_mae = mean_absolute_error(ts, y_pred)
                    metric_mape = float(np.mean(np.abs((ts - y_pred) / ts.replace(0, 1))) * 100)
        except Exception as e:
            logger.warning("SARIMAX fit failed: %s", e)

    # Fallback to Holt-Winters
    if model_used == "none":
        try:
            seasonal_type = 'add' if n >= 2 * s else None
            hw_model = ExponentialSmoothing(
                ts, trend='add',
                seasonal=seasonal_type,
                seasonal_periods=s if seasonal_type else None
            )
            hw_results = hw_model.fit()
            y_pred = hw_results.fittedvalues.fillna(0)
            
            if not np.any(np.isnan(y_pred)) and not np.any(np.isinf(y_pred)):
                metric_r2 = r2_score(ts, y_pred)
                model_used = "holt_winters"
                forecast_values = hw_results.forecast(periods).fillna(0)
                resid_std = float((ts - y_pred).std())
                conf_int_lower = (forecast_values - 1.96 * resid_std).tolist()
                conf_int_upper = (forecast_values + 1.96 * resid_std).tolist()
                metric_mae = mean_absolute_error(ts, y_pred)
                metric_mape = float(np.mean(np.abs((ts - y_pred) / ts.replace(0, 1))) * 100)
        except Exception as e:
            logger.error("Holt-Winters failed: %s", e)
            return _error_response(currency, "Forecasting models failed due to data variance.")

    # ── Gate 2: R² < 0 → invalid ──────────────────────────────────────────────
    if metric_r2 < 0 or np.isnan(metric_r2):
        return _invalid_response(
            historical_list, currency,
            "Forecast not reliable due to poor model fit (R² < 0)."
        )

    # ── Step 5: Reliability Tier ───────────────────────────────────────────────
    if metric_r2 >= 0.6 and cv <= 0.8:
        reliability = "high"
    elif metric_r2 >= 0.3:
        reliability = "medium"
    else:
        reliability = "low"

    # ── Step 6: Trend Direction (linear regression on historical series) ───────
    ts_values = ts.values
    slope = float(np.polyfit(range(len(ts_values)), ts_values, 1)[0])
    if slope > 0.01:
        trend = "increasing"
    elif slope < -0.01:
        trend = "decreasing"
    else:
        trend = "stable"

    # ── Step 7: Output ─────────────────────────────────────────────────────────
    future_index = pd.date_range(start=ts.index[-1], periods=periods + 1, freq="MS")[1:]

    if ts.min() >= 0:
        conf_int_lower = [max(0.0, float(x)) for x in conf_int_lower]

    return {
        "status": "success",
        "success": True,
        "currency": currency,
        "historical": historical_list,
        "forecast": [
            {"period": str(idx.date()), "value": float(val)}
            for idx, val in zip(future_index, forecast_values)
        ],
        "confidence_intervals": {
            "lower": [float(x) for x in conf_int_lower],
            "upper": [float(x) for x in conf_int_upper],
        },
        "metrics": {
            "r2": round(float(metric_r2), 4),
            "mae": round(float(metric_mae), 2),
            "mape": round(float(metric_mape), 2),
            "reliability": reliability,
            "model_used": model_used,
        },
        "trend": trend,
        "period_context": {
            "current_period": rev_result["current_period"],
            "previous_period": rev_result["previous_period"],
            "n_months": rev_result["n_months"],
        },
        "volatility": volatility,
        "error": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Private Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _invalid_response(historical: list, currency: str, msg: str) -> Dict:
    return {
        "status": "invalid_forecast",
        "success": False,
        "currency": currency,
        "historical": historical,
        "forecast": [],
        "confidence_intervals": {"lower": [], "upper": []},
        "metrics": {"r2": 0.0, "mae": 0.0, "reliability": "invalid", "model_used": "none"},
        "trend": "stable",
        "volatility": {"cv": 0.0, "stability_label": "Insufficient Data"},
        "error": msg,
        "message": msg,
    }


def _error_response(currency: str, msg: str) -> Dict:
    return {
        "status": "error",
        "success": False,
        "currency": currency,
        "historical": [],
        "forecast": [],
        "confidence_intervals": {"lower": [], "upper": []},
        "metrics": {"r2": 0.0, "mae": 0.0, "reliability": "invalid", "model_used": "none"},
        "trend": "stable",
        "volatility": {"cv": 0.0, "stability_label": "Insufficient Data"},
        "error": msg,
        "message": msg,
    }
