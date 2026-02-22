"""Debug script: runs the summary endpoint logic directly."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app.services.analytics import run_sql
import pandas as pd

try:
    rows = run_sql(engine, 'SELECT * FROM "sales_data" LIMIT 1000')
    df = pd.DataFrame(rows)
    print(f"DF shape: {df.shape}")
    print("Columns:", df.columns.tolist()[:12])
except Exception as e:
    print(f"DB error: {e}")
    sys.exit(1)

from app.services.revenue_engine import _try_compute_revenue, detect_date_column, detect_revenue_column
df2 = _try_compute_revenue(df)
print("Revenue col exists:", 'Revenue' in df2.columns)
print("date_col:", detect_date_column(df2))
print("rev_col:", detect_revenue_column(df2))

from app.services.industry_detection import detect_industry
try:
    industry, _ = detect_industry(df2, df2.columns.tolist())
    print("Industry:", industry)
except Exception as e:
    print("Industry detect failed:", e)

from app.services.profiling import profile_dataset
try:
    profile = profile_dataset(df2)
    metrics = profile.get('computed_metrics', [])
    print("Metrics:", [(m['label'], round(m['value'],2)) for m in metrics])
    column_stats = profile.get('column_stats', {})
    print("Column stats keys (first 5):", list(column_stats.keys())[:5])
except Exception as e:
    print("Profile failed:", traceback.format_exc())

from app.utils.file_processing import detect_currency, format_currency
currency = detect_currency(df2)
print("Currency detected:", currency)
print("format_currency(1250000):", format_currency(1_250_000, currency))
