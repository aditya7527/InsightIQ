
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, r2_score

logger = logging.getLogger(__name__)

def generate_forecast(df: pd.DataFrame, revenue_column: str, date_column: str, periods: int = 3) -> Dict:
    """
    Enterprise-grade forecasting engine.
    Implements strict preprocessing, volatility-based aggregation,
    hierarchical model selection, and rigorous reliability gating.
    """
    try:
        # 1. Preprocessing Layer
        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column])
        df = df.sort_values(by=date_column)
        df = df.set_index(date_column)
        
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        # 2. Automatic Frequency Detection
        inferred_freq = pd.infer_freq(df.index)
        if not inferred_freq:
            # Heuristic fallback
            diff_days = pd.Series(df.index).diff().dt.days.median()
            if diff_days <= 2:
                inferred_freq = 'D'
            elif diff_days <= 10:
                inferred_freq = 'W'
            else:
                inferred_freq = 'MS'
        
        # Initial resampling
        ts = df[revenue_column].resample(inferred_freq).sum().fillna(0)
        aggregation_applied = False

        # 3. Volatility & Density Detection
        mean_rev = ts.mean()
        std_rev = ts.std()
        cv = std_rev / abs(mean_rev) if abs(mean_rev) > 0 else 10.0
        num_points = len(ts)
        is_daily = inferred_freq and 'D' in inferred_freq.upper()
        
        logger.info(f"Forecasting: Freq={inferred_freq}, Points={num_points}, CV={cv:.2f}")

        # If daily data is detected, aggregate to Monthly for a clean 'Revenue Trend' view.
        # Daily spikes are almost always visual noise for forecasting.
        if is_daily:
            ts = df[revenue_column].resample("MS").sum().fillna(0)
            inferred_freq = "MS"
            aggregation_applied = True
            logger.info("Enforced monthly aggregation for a smooth executive line curve.")
        elif num_points > 60:
            # High density non-daily: Aggregate to Monthly or Weekly depending on existing frequency
            if 'W' in inferred_freq.upper():
                ts = df[revenue_column].resample("MS").sum().fillna(0)
                inferred_freq = "MS"
                aggregation_applied = True
                logger.info("Aggregated weekly data to monthly for visual clarity.")

        # Data Length Check
        n = len(ts)
        if n < 12:
            return {
                "status": "insufficient_data",
                "aggregation_applied": aggregation_applied,
                "message": "Insufficient historical data (minimum 12 periods required).",
                "historical": [{"date": str(i.date()), "value": float(v)} for i, v in ts.items()],
                "success": False
            }

        # 4. Hierarchical Model Strategy
        model_used = "none"
        metric_r2 = -1.0
        metric_mae = 0.0
        metric_mape = 0.0
        forecast_values = []
        conf_int_lower = []
        conf_int_upper = []
        
        s = 12 if 'M' in inferred_freq.upper() else (52 if 'W' in inferred_freq.upper() else 7)
        
        # Strategy: SARIMAX if N >= 18, else HW
        if n >= 18:
            try:
                # SARIMAX(1,1,1)(1,1,1,s)
                model = SARIMAX(ts, order=(1,1,1), seasonal_order=(1,1,1,s),
                                enforce_stationarity=False, enforce_invertibility=False)
                results = model.fit(disp=False)
                
                # Validation (In-sample)
                y_pred = results.fittedvalues
                metric_r2 = r2_score(ts, y_pred)
                
                if metric_r2 >= 0:
                    model_used = "sarimax"
                    f_res = results.get_forecast(steps=periods)
                    forecast_values = f_res.predicted_mean
                    ci = f_res.conf_int()
                    conf_int_lower = ci.iloc[:, 0].tolist()
                    conf_int_upper = ci.iloc[:, 1].tolist()
                    metric_mae = mean_absolute_error(ts, y_pred)
                    metric_mape = np.mean(np.abs((ts - y_pred) / ts.replace(0, 1))) * 100
            except Exception as e:
                logger.warning(f"SARIMAX fit failed: {e}")

        # Fallback to Holt-Winters if SARIMAX failed or R2 < 0
        if model_used == "none":
            try:
                # Holt-Winters
                seasonal_type = 'add' if n >= 2*s else None
                model = ExponentialSmoothing(ts, trend='add', seasonal=seasonal_type, seasonal_periods=s if seasonal_type else None)
                results = model.fit()
                
                y_pred = results.fittedvalues
                metric_r2 = r2_score(ts, y_pred)
                model_used = "holt_winters"
                
                forecast_values = results.forecast(periods)
                # HW analytical CI is complex; use residual std dev
                resid_std = (ts - y_pred).std()
                conf_int_lower = (forecast_values - 1.96 * resid_std).tolist()
                conf_int_upper = (forecast_values + 1.96 * resid_std).tolist()
                metric_mae = mean_absolute_error(ts, y_pred)
                metric_mape = np.mean(np.abs((ts - y_pred) / ts.replace(0, 1))) * 100
            except Exception as e:
                logger.error(f"Holt-Winters failed: {e}")
                return _empty_forecast_response("Forecasting models failed.")

        # 5. Reliability Gating
        reliability = "high"
        if metric_r2 < 0.3 or n < 18 or metric_mape > 35:
            reliability = "low"
        elif metric_r2 < 0.6:
            reliability = "medium"
            
        if metric_r2 < 0:
            return {
                "status": "unreliable",
                "message": "Data volatility prevents statistically meaningful forecasting.",
                "aggregation_applied": aggregation_applied,
                "metrics": {"r2": round(metric_r2, 4), "reliability": "invalid"},
                "success": False
            }

        # 6. Trend Detection
        slope = np.polyfit(range(len(forecast_values)), forecast_values, 1)[0]
        threshold = 0.02 * ts.mean()
        if abs(slope) < threshold:
            trend = "stable"
        elif slope > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        # 7. Output Construction
        future_index = pd.date_range(start=ts.index[-1], periods=periods+1, freq=inferred_freq)[1:]
        
        return {
            "status": "success",
            "aggregation_applied": aggregation_applied,
            "historical": [{"date": str(idx.date()), "value": float(val)} for idx, val in ts.items()],
            "forecast": [{"period": str(idx.date()), "value": float(val)} for idx, val in zip(future_index, forecast_values)],
            "confidence_intervals": [
                {
                    "period": str(idx.date()),
                    "lower": max(0, float(l)),
                    "upper": float(u)
                } for idx, l, u in zip(future_index, conf_int_lower, conf_int_upper)
            ],
            "metrics": {
                "r2": round(float(metric_r2), 4),
                "mae": round(float(metric_mae), 2),
                "mape": round(float(metric_mape), 2),
                "reliability": reliability,
                "model_used": model_used
            },
            "trend": trend,
            "success": True
        }

    except Exception as e:
        logger.error(f"Global forecasting error: {e}")
        return _empty_forecast_response(str(e))

def _empty_forecast_response(msg: str):
    return {
        "historical": [],
        "forecast": [],
        "confidence_intervals": [],
        "metrics": {"r2": 0.0, "mae": 0.0, "reliability": "low"},
        "trend": "stable",
        "success": False,
        "message": msg
    }
