import sqlite3
import pandas as pd
from app.forecasting.models import auto_detect_revenue_column

conn = sqlite3.connect('insightiq.db')
query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';"
tables = pd.read_sql(query, conn)
if not tables.empty:
    latest_table = tables['name'].iloc[-1]
    df = pd.read_sql(f"SELECT * FROM '{latest_table}'", conn)
    col = auto_detect_revenue_column(df)
    print("Auto detected revenue column:", col)
