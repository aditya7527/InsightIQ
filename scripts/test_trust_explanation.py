import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.trust_engine import compute_trust_index, generate_trust_explanation, TRUST_WEIGHTS

def test_weighted_sum_matches_score():
    """Sum(weighted_contribution) == overall_score ± 0.01"""
    quality_score = 0.92
    forecast_score = 0.77
    sig_score = 0.30
    stability_score = 0.88
    sample_score = 0.70
    
    expected_score = (
        quality_score * TRUST_WEIGHTS["Data Quality"] +
        forecast_score * TRUST_WEIGHTS["Forecast Reliability"] +
        sig_score * TRUST_WEIGHTS["Statistical Significance"] +
        stability_score * TRUST_WEIGHTS["Revenue Stability"] +
        sample_score * TRUST_WEIGHTS["Sample Strength"]
    )

    res = generate_trust_explanation(
        quality_score=quality_score,
        forecast_score=forecast_score,
        sig_score=sig_score,
        stability_score=stability_score,
        sample_score=sample_score,
        overall_score=expected_score
    )
    
    comp_sum = sum(c["weighted_contribution"] for c in res["components"])
    assert abs(comp_sum - expected_score) < 0.02, f"Weighted sum {comp_sum} does not match expected {expected_score}"

def test_limiting_factor_logic():
    """Limiting factor always matches lowest score"""
    res = generate_trust_explanation(
        quality_score=0.10, # Very low
        forecast_score=0.90,
        sig_score=0.90,
        stability_score=0.90,
        sample_score=0.90,
        overall_score=0.75
    )
    assert res["limiting_factor"] == "Data Quality"
    
    res2 = generate_trust_explanation(
        quality_score=0.90,
        forecast_score=0.90,
        sig_score=0.05, # Lowest
        stability_score=0.90,
        sample_score=0.90,
        overall_score=0.75
    )
    assert res2["limiting_factor"] == "Statistical Significance"

def test_confidence_category_bands():
    """Confidence category matches score band"""
    df = pd.DataFrame({'a': [1]})
    ms = pd.Series([1])
    
    # Very High: >= 0.85
    res_vh = compute_trust_index(df, ms, {'r2': 0.9}, {'p_value': 0.001}, 0.0)
    assert res_vh["trust_label"] == "Very High Analytical Confidence"
    
    # Low: < 0.50
    res_low = compute_trust_index(df, ms, {'r2': 0.1}, {'p_value': 0.5}, 1.0)
    assert res_low["trust_label"] == "Low Analytical Confidence"

if __name__ == "__main__":
    try:
        test_weighted_sum_matches_score()
        test_limiting_factor_logic()
        test_confidence_category_bands()
        print("ALL TESTS PASSED")
    except Exception as e:
        import traceback
        print(f"TEST FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)
