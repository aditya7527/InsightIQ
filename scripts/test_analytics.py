
import pandas as pd
import numpy as np
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.forecasting_service import generate_forecast
from app.services.root_cause_analysis import analyze_root_causes
from app.services.narrative_service import generate_summary

def test_forecasting():
    print("\n=== Testing Forecasting ===")
    
    # 1. Linear Trend (High Reliability Expected)
    dates = pd.date_range(start='2020-01-01', periods=36, freq='MS')
    values = np.linspace(100, 500, 36) # Perfect linear growth
    df = pd.DataFrame({'date': dates, 'revenue': values})
    
    print("Test 1: Linear Datset")
    res = generate_forecast(df, 'revenue', 'date', periods=3)
    print(f"Success: {res['success']}")
    print(f"Model: {res['metrics']['model_used']}")
    print(f"R2: {res['metrics']['r2']}")
    print(f"Reliability: {res['metrics']['reliability']}")
    
    if res['metrics']['reliability'] != 'high':
        print("❌ FAILED: Expected HIGH reliability for linear data")
    else:
        print("✅ PASSED: Linear reliability")

    # 2. Random Noise (Low Reliability Expected)
    np.random.seed(42)
    values_noise = np.random.normal(100, 50, 36)
    df_noise = pd.DataFrame({'date': dates, 'revenue': values_noise})
    
    print("\nTest 2: Noisy Dataset")
    res_noise = generate_forecast(df_noise, 'revenue', 'date', periods=3)
    print(f"Reliability: {res_noise['metrics']['reliability']} (R2={res_noise['metrics']['r2']})")
    
    if res_noise['metrics']['reliability'] == 'high':
        print("❌ FAILED: Expected LOW/MEDIUM reliability for noise")
    else:
         print("✅ PASSED: Noisy reliability")

    # 3. Seasonality (SARIMAX Expected)
    # Sine wave + Trend
    x = np.arange(48)
    seasonal = 50 * np.sin(2 * np.pi * x / 12)
    trend = 5 * x
    values_seas = 200 + trend + seasonal
    df_seas = pd.DataFrame({'date': pd.date_range(start='2020-01-01', periods=48, freq='MS'), 'revenue': values_seas})
    
    print("\nTest 3: Seasonal Dataset")
    res_seas = generate_forecast(df_seas, 'revenue', 'date', periods=3)
    print(f"Model: {res_seas['metrics']['model_used']}")
    
    if 'sarimax' in res_seas['metrics']['model_used']:
         print("✅ PASSED: SARIMAX selected")
    else:
         print(f"⚠️ NOTE: Model used was {res_seas['metrics']['model_used']}")


def test_root_cause():
    print("\n=== Testing Root Cause Analysis ===")
    
    # Setup Dataframe
    # Period 1: Product A=1000, Product B=500 -> Total 1500
    # Period 2: Product A=500, Product B=500  -> Total 1000 (Drop of 500)
    # Impact: A = -500, B = 0
    # Total Abs Impact = 500
    # Norm Pct: A = 100%
    
    data = [
        {'date': '2023-01-01', 'id': 1, 'Product': 'A', 'Revenue': 1000},
        {'date': '2023-01-01', 'id': 2, 'Product': 'B', 'Revenue': 500},
        {'date': '2023-02-01', 'id': 3, 'Product': 'A', 'Revenue': 500},
        {'date': '2023-02-01', 'id': 4, 'Product': 'B', 'Revenue': 500},
    ]
    df = pd.DataFrame(data)
    
    res = analyze_root_causes(df, 'Revenue', group_cols=['Product'], compare_periods=True)
    
    print(f"Change Pct: {res['kpi_change_percent']}%")
    drivers = res['top_drivers']
    print(f"Drivers found: {len(drivers)}")
    
    for d in drivers:
        print(f"  {d['name']}: {d['impact_value']} (Norm: {d['normalized_percent']}%)")
        
    if len(drivers) > 0 and drivers[0]['normalized_percent'] == 100.0:
        print("✅ PASSED: Normalization check (100% impact)")
    else:
        print("❌ FAILED: Normalization check")
        
    # Check for >100% bug prevention
    # Scenario: A=+100, B=-50. Total Change = +50.
    # Old logic: Impact A = 100 / 50 = 200% (BUG)
    # New logic: Abs Impact = 150. A = 100/150 = 66.6%. B = 50/150 = 33.3%.
    
    data2 = [
        {'date': '2023-01-01', 'Product': 'A', 'Revenue': 100},
        {'date': '2023-01-01', 'Product': 'B', 'Revenue': 100},
        {'date': '2023-02-01', 'Product': 'A', 'Revenue': 200}, # +100
        {'date': '2023-02-01', 'Product': 'B', 'Revenue': 50},  # -50
    ]
    df2 = pd.DataFrame(data2)
    res2 = analyze_root_causes(df2, 'Revenue', group_cols=['Product'])
    
    print("\nTest 2: Mixed Direction (>100% Bug Check)")
    drivers2 = res2['top_drivers']
    for d in drivers2:
        print(f"  {d['name']}: {d['impact_value']} (Norm: {d['normalized_percent']}%)")
        if d['normalized_percent'] > 100:
            print("❌ FAILED: Found >100% contribution!")
            return
            
    print("✅ PASSED: No drivers > 100%")


if __name__ == "__main__":
    try:
        test_forecasting()
        test_root_cause()
        print("\n✅ All Tests Finished.")
    except Exception as e:
        print(f"\n❌ CRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()
