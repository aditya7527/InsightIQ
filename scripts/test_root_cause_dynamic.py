
import pandas as pd
import numpy as np
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.root_cause_analysis import analyze_root_causes

def test_dynamic_rca():
    print("=== Testing Dynamic Root Cause Analysis ===")
    
    # Dataset with unusual dimensions (Marketing Channel, Payment Method)
    dates = pd.date_range(start="2023-01-01", periods=10, freq="MS").tolist() * 5
    channels = ["Email", "SEO", "PPC", "Social", "Direct"] * 10
    payments = ["Credit Card", "PayPal", "Bank Transfer", "Credit Card", "PayPal"] * 10
    
    # Correct distribution: 5 observations per month, each a different channel
    data = []
    for m_idx in range(10):
        d = dates[m_idx]
        for c_idx, channel in enumerate(["Email", "SEO", "PPC", "Social", "Direct"]):
            p = ["Credit Card", "PayPal"][c_idx % 2]
            val = 1000 + np.random.normal(0, 5)
            # Impact: PPC drops only in the LAST month
            if m_idx == 9 and channel == "PPC":
                val = 50 # 95% drop
            data.append({"OrderDate": d, "Channel": channel, "PayMethod": p, "Sales": val})
        
    df = pd.DataFrame(data)
    print(f"Dataframe Sample:\n{df.head(10)}")
    print(f"Dataframe Dtypes:\n{df.dtypes}")
    print(f"Unique dates: {df['OrderDate'].nunique()}")
    
    latest_month = df['OrderDate'].max()
    prev_month = df[df['OrderDate'] < latest_month]['OrderDate'].max()
    print(f"Latest Month: {latest_month}")
    print(f"Prev Month: {prev_month}")
    print(f"Latest Month Total: {df[df['OrderDate'] == latest_month]['Sales'].sum()}")
    print(f"Prev Month Total: {df[df['OrderDate'] == prev_month]['Sales'].sum()}")
    
    print("Running analyze_root_causes on custom dimension 'Channel'...")
    res = analyze_root_causes(df, "Sales")
    
    print(f"Result Keys: {list(res.keys())}")
    print(f"Summary: {res.get('insight_summary')}")
    print(f"KPI Change %: {res.get('kpi_change_percent')}")
    print(f"AI Generated: {res.get('ai_generated')}")
    
    drivers = res.get('top_drivers', [])
    print(f"Top Drivers Found: {len(drivers)}")
    
    for d in drivers:
        print(f" - [{d['dimension']}] {d['name']}: {d['normalized_percent']}% ({d['direction']})")
        
    # Check if 'Channel' was detected (it's not hardcoded in the original version)
    detected_dims = set(d['dimension'] for d in drivers)
    if not drivers:
        print("[FAIL] No drivers found!")
        sys.exit(1)
        
    assert "Channel" in detected_dims or "PayMethod" in detected_dims
    print("[SUCCESS] Dynamic dimension detection verified!")

if __name__ == "__main__":
    test_dynamic_rca()
