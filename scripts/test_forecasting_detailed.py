import sqlite3
import pandas as pd
from app.services.forecasting_service import generate_forecast
from app.forecasting.models import auto_detect_date_column, auto_detect_revenue_column
import warnings
warnings.filterwarnings("ignore")

conn = sqlite3.connect('insightiq.db')
query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';"
tables = pd.read_sql(query, conn)
for table in tables['name']:
    df = pd.read_sql(f"SELECT * FROM '{table}'", conn)
    date_col = auto_detect_date_column(df)
    rev_col = auto_detect_revenue_column(df)
    if date_col and rev_col and len(df) > 1000:  # test superstore
        print(f"Testing {table} with length {len(df)}")
        try:
            res = generate_forecast(df, rev_col, date_col, periods=3)
            print("Status:", res.get("status"), "Message:", res.get("error"))
            if "metrics" in res:
                print("Metrics:", res["metrics"])
        except Exception as e:
            print("Exception:", e)
        print("---")
