import pandas as pd
import os
import glob
from app.services.forecasting_service import generate_forecast

def check_latest_file():
    upload_dir = r"c:\Users\ASUS\Desktop\Inside\data\uploads"
    files = glob.glob(os.path.join(upload_dir, "*"))
    if not files:
        print("No files found in upload directory.")
        return

    latest_file = max(files, key=os.path.getctime)
    print(f"Checking latest file: {latest_file}")
    
    try:
        if latest_file.endswith('.csv'):
            df = pd.read_csv(latest_file)
        else:
            df = pd.read_excel(latest_file)
            
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        
        # Try to detect date and revenue
        from app.forecasting.models import auto_detect_date_column, auto_detect_revenue_column
        date_col = auto_detect_date_column(df)
        rev_col = auto_detect_revenue_column(df)
        
        print(f"Detected Date Column: {date_col}")
        print(f"Detected Revenue Column: {rev_col}")
        
        if date_col and rev_col:
            # Check row count after dropna
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df_clean = df.dropna(subset=[date_col])
            print(f"Rows with valid date: {len(df_clean)}")
            
            # Check volatility
            ts = df_clean.set_index(date_col)[rev_col].resample('MS').sum().fillna(0)
            cv = ts.std() / ts.mean() if ts.mean() != 0 else 0
            print(f"Monthly Volatility (CV): {cv:.2f}")
            print(f"Resampled Points: {len(ts)}")

            # Run forecast
            res = generate_forecast(df, rev_col, date_col, periods=3)
            import json
            print("\n--- Full JSON Result ---")
            print(json.dumps(res, default=str))

    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    check_latest_file()
