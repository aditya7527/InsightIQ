"""
Root Cause Analysis Engine — consumes Revenue Engine output.

# DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
Period comparison references current_period/previous_period from
compute_monthly_revenue() strictly. No independent re-aggregation.
"""
import os
import pandas as pd
import numpy as np
from scipy.stats import ttest_ind, mannwhitneyu, shapiro
from typing import Dict, List, Optional
import logging

from app.services.revenue_engine import (
    compute_monthly_revenue,
    detect_date_column,
    detect_revenue_column,
    _try_compute_revenue,
    get_monthly_series_from_result
)
from app.services.revenue_bridge_service import compute_revenue_bridge
from app.utils.file_processing import detect_currency, format_currency

logger = logging.getLogger(__name__)

ID_PATTERNS = ['id', 'no', 'code', 'key', 'uuid', 'index', 'invoiceno', 'stockcode', 'customerid']


def _is_id(col: str) -> bool:
    cleaned = col.lower().replace('_', '').replace(' ', '')
    return any(p in cleaned for p in ID_PATTERNS)


def analyze_root_causes(
    df: pd.DataFrame,
    metric_col: str,
    group_cols: Optional[List[str]] = None,
    compare_periods: bool = True,
    rev_result: Optional[Dict] = None,
) -> Dict:
    """
    Analyze root causes using revenue_engine for period baselines.
    No independent re-aggregation. Changes must be >= 3% to trigger driver scan.

    # DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
    """
    try:
        # ── Step 1: Ensure revenue column exists ──────────────────────────────
        df = _try_compute_revenue(df)
        if metric_col not in df.columns:
            metric_col = detect_revenue_column(df) or metric_col
        if metric_col not in df.columns:
            return _safe_response(metric_col, 'Column not found')

        # ── Step 2: Detect date column ────────────────────────────────────────
        date_col = detect_date_column(df)
        if not date_col:
            return _static_group_analysis(df, metric_col, group_cols)

        # ── Step 3: Delegate period computation to Revenue Engine ─────────────
        if rev_result is None:
            currency = detect_currency(df)
            rev_result = compute_monthly_revenue(df, date_col, metric_col, currency=currency)
        else:
            currency = rev_result.get("currency", detect_currency(df))

        if rev_result["status"] == "insufficient_data":
            return _static_group_analysis(df, metric_col, group_cols)

        val_latest = rev_result["current_value"]
        val_prev   = rev_result["previous_value"]
        change_pct = rev_result["change_percent"]     # already precise
        latest_str = rev_result["current_period"]
        previous_str = rev_result["previous_period"]

        logger.debug(
            "RCA baseline (from revenue_engine): prev=%s=%s  curr=%s=%s  change=%.4f%%",
            previous_str, val_prev, latest_str, val_latest, change_pct,
        )

        # ── Step 4: Trigger Condition (>= 1% change) ──────────────────────────
        if abs(change_pct) < 1.0 or val_latest < 500:
            return {
                "current_period": latest_str,
                "previous_period": previous_str,
                "current_value": float(val_latest),
                "previous_value": float(val_prev),
                "change_percent": round(change_pct, 4),
                "top_drivers": [],
                "insight_summary": "No statistically meaningful change detected.",
                "recommendations": [],
                "waterfall": {"previous_value": val_prev, "components": [], "current_value": val_latest},
            }

        # ── Step 5: Period slicing (using Revenue Engine periods) ─────────────
        # Use the same date column, parse and slice by month string
        ts = df.copy()
        ts['_dt'] = pd.to_datetime(ts[date_col], errors='coerce')
        ts = ts.dropna(subset=['_dt'])
        ts['_month'] = ts['_dt'].dt.to_period('M')

        df_latest   = ts[ts['_month'].astype(str) == latest_str]
        df_previous = ts[ts['_month'].astype(str) == previous_str]
        
        # ── Step 5.5: Statistical Significance ────────────────────────────────
        curr_dist = df_latest[metric_col].dropna().values
        prev_dist = df_previous[metric_col].dropna().values
        
        stat_val, p_value = 1.0, 1.0
        is_significant = False
        
        if len(curr_dist) >= 3 and len(prev_dist) >= 3:
            _, p_curr_norm = shapiro(curr_dist)
            _, p_prev_norm = shapiro(prev_dist)
            normality_passed = (p_curr_norm > 0.05) and (p_prev_norm > 0.05)
            if normality_passed:
                stat_val, p_value = ttest_ind(prev_dist, curr_dist, equal_var=False)
            else:
                stat_val, p_value = mannwhitneyu(prev_dist, curr_dist, alternative='two-sided')
            is_significant = bool(p_value < 0.05)

        # ── Step 5.6: Anomaly Detection ───────────────────────────────────────
        monthly_series = get_monthly_series_from_result(rev_result)
        anomaly_detected = False
        anomaly_confidence = 0.0
        if len(monthly_series) >= 3:
            mean_rev = float(monthly_series.mean())
            std_rev = float(monthly_series.std())
            z_score = abs(val_latest - mean_rev) / std_rev if std_rev > 0 else 0
            if z_score > 3:
                anomaly_detected = True
                anomaly_confidence = 0.94

        # ── Step 6: Dimension Scan ────────────────────────────────────────────
        potential_dims = [
            c for c in df.columns
            if c not in [metric_col, date_col, '_dt', '_month']
            and not _is_id(c)
            and str(df[c].dtype) in ('object', 'category', 'string')
            and df[c].nunique() <= 50
        ]

        raw_impacts = []
        for col in potential_dims:
            l_grp = df_latest.groupby(col)[metric_col].sum()
            p_grp = df_previous.groupby(col)[metric_col].sum()
            all_keys = set(l_grp.index) | set(p_grp.index)

            for k in all_keys:
                if pd.isna(k) or k == '':
                    continue
                imp = float(l_grp.get(k, 0)) - float(p_grp.get(k, 0))
                if abs(imp) > 0.01:
                    raw_impacts.append({
                        'dimension': col,
                        'name': str(k),
                        'impact_value': imp,
                    })

        # Sort by absolute impact
        raw_impacts.sort(key=lambda x: abs(x['impact_value']), reverse=True)

        # ── Step 7: Normalise to percentages & Driver Strength ─────────────────
        final_drivers = []
        
        if raw_impacts:
            top_six = raw_impacts[:6]
            abs_impact_sum = sum(abs(x['impact_value']) for x in top_six)
            if abs_impact_sum > 0:
                for item in top_six:
                    norm_pct = (abs(item['impact_value']) / abs_impact_sum) * 100
                    driver_delta = item['impact_value']
                    # Shapley-style normalization: sum of top drivers strength = 1.0
                    driver_strength = abs(driver_delta) / abs_impact_sum
                    
                    final_drivers.append({
                        'dimension': item['dimension'],
                        'value': item['name'],
                        'delta_value': driver_delta,
                        'normalized_percent': round(norm_pct, 1),
                        'direction': 'positive' if driver_delta > 0 else 'negative',
                        'contribution': round(driver_strength, 4)
                    })

        # ── Step 8: Narrative (AI may narrate only — no new numbers) ──────────
        val_prev_str = format_currency(val_prev, currency)
        val_latest_str = format_currency(val_latest, currency)
        dir_word = "increased" if change_pct >= 0 else "decreased"
        raw_summary = (
            f"{metric_col} {dir_word} {abs(change_pct):.2f}% "
            f"from {previous_str} to {latest_str} "
            f"({val_prev_str} \u2192 {val_latest_str}). "
            f"Highest contribution to month-over-month change is shown above."
        )
        insight_summary = raw_summary
        recommendations = _generate_recommendations(final_drivers, change_pct)
        ai_narrative = None

        # Skip AI call when INSIGHTIQ_NO_AI=1 (used by integrity test suite)
        _skip_ai = os.environ.get("INSIGHTIQ_NO_AI", "0") == "1"
        if not _skip_ai:
            try:
                from app.ai.gpt_service import query_gpt
                import json
                payload = {"metrics_summary": raw_summary, "drivers": final_drivers}
                prompt = (
                    "You are a business intelligence expert. "
                    "Include the metrics_summary exactly as your first sentence. "
                    "Add 1 professional sentence about the highest contributing driver. "
                    "Do not compute any new numbers. Do not guess.\n"
                    f"Data: {payload}\n"
                    'Format as JSON: {"summary": "...", "recommendations": ["...", "...", "..."]}'
                )
                ai_raw = query_gpt(prompt, max_tokens=300)
                start = ai_raw.find('{')
                end   = ai_raw.rfind('}') + 1
                if start != -1 and end > start:
                    ai_data = json.loads(ai_raw[start:end])
                    if 'error' not in ai_data:
                        insight_summary  = ai_data.get('summary', insight_summary)
                        recommendations  = ai_data.get('recommendations', recommendations)
                        ai_narrative = True
            except Exception as ai_err:
                logger.warning("AI Narrative failed: %s", ai_err)

        # ── Step 9: Waterfall bridge fallback ─────────────────────────────────────
        try:
            monthly_series = get_monthly_series_from_result(rev_result)
            waterfall = compute_revenue_bridge(monthly_series, df, metric_col, date_col)
        except Exception as e:
            logger.warning("Failed to compute revenue bridge: %s", e)
            waterfall = {"previous_value": val_prev, "components": [], "current_value": val_latest}

        return {
            'current_period':   latest_str,
            'previous_period':  previous_str,
            'current_value':    float(val_latest),
            'previous_value':   float(val_prev),
            'change_percent':   round(change_pct, 4),
            'p_value':          float(p_value),
            'is_significant':   is_significant,
            'anomaly_detected': anomaly_detected,
            'anomaly_confidence': anomaly_confidence,
            'top_drivers':      final_drivers,
            'insight_summary':  insight_summary,
            'recommendations':  recommendations,
            'ai_generated':     ai_narrative,
            'waterfall':        waterfall,
        }

    except Exception as e:
        logger.error("Root cause error: %s", e)
        return _safe_response(metric_col, "Root cause analysis failed due to data inconsistencies.")


def _static_group_analysis(df, metric_col, group_cols):
    """Fallback when no time data is available."""
    total = df[metric_col].sum()
    if total == 0:
        return _safe_response(metric_col, 'Metric total is zero')

    drivers = []
    if group_cols:
        for gc in group_cols:
            if gc in df.columns and not _is_id(gc):
                grouped = df.groupby(gc)[metric_col].sum().sort_values(ascending=False).head(5)
                for name, val in grouped.items():
                    contribution = (val / total) * 100 if total > 0 else 0
                    drivers.append({
                        'dimension': gc,
                        'value': str(name),
                        'delta_value': float(val),
                        'normalized_percent': round(contribution, 1),
                        'direction': 'positive',
                    })

    drivers = sorted(drivers, key=lambda x: x['normalized_percent'], reverse=True)[:5]

    return {
        'current_period': None,
        'previous_period': None,
        'current_value': float(total),
        'previous_value': None,
        'change_percent': None,
        'p_value': 1.0,
        'is_significant': False,
        'anomaly_detected': False,
        'anomaly_confidence': 0.0,
        'top_drivers': drivers,
        'insight_summary': f"Static analysis: Top drivers ranked by contribution to {metric_col}.",
        'recommendations': _generate_recommendations(drivers, 0),
        'waterfall': None,
    }


def _safe_response(metric_col: str, error: str = '') -> Dict:
    """Return a safe, never-undefined response."""
    return {
        'current_period': None,
        'previous_period': None,
        'current_value': 0.0,
        'previous_value': None,
        'change_percent': None,
        'p_value': 1.0,
        'is_significant': False,
        'anomaly_detected': False,
        'anomaly_confidence': 0.0,
        'top_drivers': [],
        'insight_summary': error or 'Not enough time-series data for root cause analysis.',
        'recommendations': ['Ensure the dataset has date and numeric columns for analysis.'],
        'waterfall': None,
    }


def _generate_recommendations(drivers: List[Dict], change_pct: float) -> List[str]:
    recs = []
    for d in drivers[:3]:
        name = d.get('value', d.get('name', 'Unknown'))
        dimension = d.get('dimension', '')
        pct = d.get('normalized_percent', d.get('contribution_percent', 0))
        direction = d.get('direction', 'positive')
        display_name = f"{name} ({dimension})" if dimension else name

        if pct > 20:
            recs.append(f"Focus on {display_name} — highest contribution to month-over-month change ({pct:.1f}%)")
        elif direction == 'negative':
            recs.append(f"Investigate decline in {display_name}")
        else:
            recs.append(f"Monitor {display_name} ({pct:.1f}% impact)")

    if change_pct is not None:
        if change_pct < -5:
            recs.append("Revenue declining — review pricing strategy and customer retention")
        elif change_pct > 10:
            recs.append("Strong growth — consider scaling operations to sustain momentum")

    if not recs:
        recs.append("No significant drivers detected — review data quality")
    return recs


def detect_anomalies(df: pd.DataFrame, metric_col: str) -> List[Dict]:
    """Detect anomalies using 2-sigma rule."""
    anomalies = []
    try:
        data = df[metric_col].dropna()
        if len(data) < 3:
            return anomalies
        mean = data.mean()
        std = data.std()
        if std == 0:
            return anomalies
        outliers = data[(data > mean + 2 * std) | (data < mean - 2 * std)]
        for idx, value in outliers.head(10).items():
            deviation = (value - mean) / std
            anomalies.append({
                'index': int(idx),
                'value': float(value),
                'mean': float(mean),
                'deviation_sigma': round(float(deviation), 2),
                'severity': 'High' if abs(deviation) > 3 else 'Medium',
            })
    except Exception as e:
        logger.warning("Anomaly detection: %s", e)
    return anomalies
