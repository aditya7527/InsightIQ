import pandas as pd
import numpy as np
from typing import Dict, Any

TRUST_WEIGHTS = {
    "Data Quality": 0.25,
    "Forecast Reliability": 0.25,
    "Statistical Significance": 0.20,
    "Revenue Stability": 0.15,
    "Sample Strength": 0.15
}

def generate_trust_explanation(
    quality_score: float,
    forecast_score: float,
    sig_score: float,
    stability_score: float,
    sample_score: float,
    overall_score: float
) -> Dict[str, Any]:
    """
    Decompose trust score into components and identify limiting factors.
    """
    components = [
        {"name": "Data Quality", "score": round(quality_score, 2), "weight": TRUST_WEIGHTS["Data Quality"]},
        {"name": "Forecast Reliability", "score": round(forecast_score, 2), "weight": TRUST_WEIGHTS["Forecast Reliability"]},
        {"name": "Statistical Significance", "score": round(sig_score, 2), "weight": TRUST_WEIGHTS["Statistical Significance"]},
        {"name": "Revenue Stability", "score": round(stability_score, 2), "weight": TRUST_WEIGHTS["Revenue Stability"]},
        {"name": "Sample Strength", "score": round(sample_score, 2), "weight": TRUST_WEIGHTS["Sample Strength"]},
    ]
    
    for c in components:
        c["weighted_contribution"] = round(c["score"] * c["weight"], 3)
        
    limiting_factor_obj = min(components, key=lambda x: x["score"])
    limiting_factor = limiting_factor_obj["name"]
    
    # Reason generation logic (deterministic)
    reasons = []
    if sig_score < 0.5:
        reasons.append("The observed change is not statistically significant (p > 0.05), reducing analytical certainty.")
    if forecast_score < 0.6:
        reasons.append("Forecast model reliability is moderate (R² below optimal threshold).")
    if sample_score < 0.6:
        reasons.append("Limited data volume reduces statistical power.")
    if quality_score < 0.7:
        reasons.append("Data quality issues (nulls or duplicates) detected in source.")
    if stability_score < 0.5:
        reasons.append("High revenue volatility makes trend detection less reliable.")

    if not reasons:
        reasons.append("Metrics consistently meet high-quality analytical thresholds.")

    return {
        "overall_score": round(overall_score, 4),
        "components": components,
        "limiting_factor": limiting_factor,
        "explanation": " ".join(reasons) if reasons else "Metrics meet quality thresholds."
    }

def compute_trust_index(
    df: pd.DataFrame,
    monthly_series: pd.Series,
    model_metrics: Dict[str, Any],
    significance_result: Dict[str, Any],
    volatility_cv: float
) -> Dict[str, Any]:
    """
    Compute a Multi-Factor Trust Index based on five core statistical constraints.
    """
    # ── Factor 1: Data Quality Score (0–1) ──
    rev_cols = [c for c in df.columns if c.lower() in ('revenue', 'sales', 'amount', 'total', 'profit', 'price')]
    rev_col = rev_cols[0] if rev_cols else df.select_dtypes(include='number').columns[0]
    
    n_rows = len(df)
    if n_rows == 0:
        return {"trust_score": 0.0, "trust_label": "Insufficient Data"}
        
    completeness_score = df[rev_col].notnull().mean()
    duplicate_ratio = df.duplicated().mean()
    
    negative_anomalies = (df[rev_col] < 0).mean()
    anomaly_penalty = max(0.0, 1.0 - (negative_anomalies * 5))
    
    quality_score = (
        completeness_score * 0.5 +
        (1 - duplicate_ratio) * 0.3 +
        anomaly_penalty * 0.2
    )
    
    # ── Factor 2: Forecast Reliability ──
    r2 = float(model_metrics.get('r2', 0.0))
    forecast_score = max(0.0, min(0.9, r2))
    
    # ── Factor 3: Statistical Significance Score ──
    p_value = float(significance_result.get('p_value', 1.0))
    if p_value < 0.01:
        sig_score = 1.0
    elif p_value < 0.05:
        sig_score = 0.8
    elif p_value < 0.10:
        sig_score = 0.6
    else:
        sig_score = 0.3
        
    # ── Factor 4: Volatility Stability ──
    try:
        cv = float(volatility_cv)
    except (ValueError, TypeError):
        cv = 1.0
    stability_score = max(0.0, 1.0 - (cv * 2))
    
    # ── Factor 5: Sample Strength ──
    num_periods = len(monthly_series) if monthly_series is not None and not monthly_series.empty else 0
    period_score = min(1.0, num_periods / 24.0)
    txn_score = min(1.0, n_rows / 5000.0)
    raw_sample = (period_score + txn_score) / 2.0
    sample_score = 0.5 + (raw_sample * 0.5)
    
    # ── Final Trust Index ──
    trust_index = (
        quality_score * TRUST_WEIGHTS["Data Quality"] +
        forecast_score * TRUST_WEIGHTS["Forecast Reliability"] +
        sig_score * TRUST_WEIGHTS["Statistical Significance"] +
        stability_score * TRUST_WEIGHTS["Revenue Stability"] +
        sample_score * TRUST_WEIGHTS["Sample Strength"]
    )
    
    final_score = min(0.97, max(0.0, trust_index))
    
    if final_score >= 0.85:
        label = "Very High Analytical Confidence"
    elif final_score >= 0.70:
        label = "High Analytical Confidence"
    elif final_score >= 0.50:
        label = "Moderate Analytical Confidence"
    else:
        label = "Low Analytical Confidence"
        
    explanation = generate_trust_explanation(
        quality_score, forecast_score, sig_score, stability_score, sample_score, final_score
    )
    explanation["trust_label"] = label
    explanation["trust_score"] = round(final_score, 4)
    
    return explanation
