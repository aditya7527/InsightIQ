import pandas as pd
import numpy as np
import logging
from app.services.forecasting_service import generate_forecast

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_forecast():
    print("Testing Forecasting Service...")
    
    # create synthetic monthly data (24 months)
    dates = pd.date_range(start='2024-01-01', periods=24, freq='M')
    # Linear trend + some noise
    values = [1000 + x * 50 + np.random.normal(0, 20) for x in range(24)]
    
    df = pd.DataFrame({'ds': dates, 'y': values})
    
    print(f"Created DataFrame with {len(df)} rows.")
    
    result = generate_forecast(df, 'y', 'ds', periods=3)
    
    print("\n--- Result ---")
    print(f"Success: {result.get('success')}")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message')}")
    if result.get('metrics'):
        print(f"R2: {result['metrics'].get('r2')}")
        print(f"Model: {result['metrics'].get('model_used')}")
    
    if result.get('forecast'):
        print(f"Forecast Points: {len(result['forecast'])}")
        print(f"First Forecast: {result['forecast'][0]}")

if __name__ == "__main__":
    try:
        test_forecast()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
