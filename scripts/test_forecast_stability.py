
import pandas as pd
import numpy as np
import sys
import os

# Add app directory to path
sys.path.append(os.getcwd())

from app.services.forecasting_service import generate_forecast

def test_forecast_stability():
    print("=== Forecasting Stability Test Suite ===\n")

    # 1. Clean Monthly Linear Data (Expect High/Medium Reliability)
    dates = pd.date_range(start="2022-01-01", periods=36, freq="MS")
    values = [1000 + i*10 + np.random.normal(0, 2) for i in range(36)]
    df_clean = pd.DataFrame({"Date": dates, "Revenue": values})
    
    res_clean = generate_forecast(df_clean, "Revenue", "Date")
    print(f"CASE 1 (Clean Monthly): Status={res_clean.get('status','success')}, Reliability={res_clean['metrics']['reliability']}, R2={res_clean['metrics']['r2']}")
    assert res_clean['success'] is True
    assert res_clean['metrics']['reliability'] in ["high", "medium"]

    # 2. Random Noise (Expect Unreliable/Invalid)
    values_noise = np.random.normal(1000, 500, 36)
    df_noise = pd.DataFrame({"Date": dates, "Revenue": values_noise})
    
    res_noise = generate_forecast(df_noise, "Revenue", "Date")
    # Low R2 or negative
    rel = res_noise.get('metrics', {}).get('reliability')
    stat = res_noise.get('status')
    print(f"CASE 2 (Noise): Status={stat}, Reliability={rel}")
    assert rel in ["low", "invalid"] or stat == "unreliable"

    # 3. Short Dataset (Expect insufficient_data)
    dates_short = pd.date_range(start="2023-01-01", periods=10, freq="MS")
    df_short = pd.DataFrame({"Date": dates_short, "Revenue": range(10)})
    
    res_short = generate_forecast(df_short, "Revenue", "Date")
    print(f"CASE 3 (Short): Status={res_short.get('status')}")
    assert res_short.get('status') == "insufficient_data"

    # 4. High Volatility Daily (Expect Auto-Aggregation)
    # Use 400 days so it has enough points (13+ months) after aggregation
    dates_daily = pd.date_range(start="2022-01-01", periods=400, freq="D")
    # High variance noise
    values_vol = [100 + (i % 7)*10 + np.random.normal(0, 150) for i in range(400)]
    df_vol = pd.DataFrame({"Date": dates_daily, "Revenue": values_vol})
    
    res_vol = generate_forecast(df_vol, "Revenue", "Date")
    print(f"CASE 4 (Volatile Daily): Status={res_vol.get('status')}, AggregationApplied={res_vol.get('aggregation_applied')}")
    # Since CV is very high, it should aggregate
    if not res_vol.get('aggregation_applied'):
        print(f"DEBUG: CV was not high enough or freq was not D. Results: {res_vol.get('metrics', {})}")
    assert res_vol.get('aggregation_applied') is True

    print("\nALL forecasting stability tests passed!")

if __name__ == "__main__":
    test_forecast_stability()
