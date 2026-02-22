import sqlite3
import pandas as pd
from app.services.forecasting_service import generate_forecast

conn = sqlite3.connect('insightiq.db')
query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';"
tables = pd.read_sql(query, conn)
if not tables.empty:
    latest_table = tables['name'].iloc[-1]
    df = pd.read_sql(f"SELECT * FROM '{latest_table}'", conn)
    
    date_cols = [c for c in df.columns if 'date' in str(c).lower() and c != '_dt']
    date_col = date_cols[0] if date_cols else None
    if not date_col and 'Order Date' in df.columns:
        date_col = 'Order Date'
        
    metric_cols = [c for c in df.columns if 'sales' in str(c).lower() or 'revenue' in str(c).lower()]
    metric_col = metric_cols[0] if metric_cols else None
    
    if date_col and metric_col:
        print('Testing', date_col, metric_col, len(df))
        res = generate_forecast(df, metric_col, date_col, periods=3)
        print('Status:', res.get('status'))
        print('Msg:', res.get('error'))
        if 'metrics' in res:
            print('Metrics:', res['metrics'])
    else:
        print('Missing cols:', df.columns)
