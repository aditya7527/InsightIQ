"""Diagnose RCA crash on a Superstore-like dataset."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["INSIGHTIQ_NO_AI"] = "1"

import pandas as pd
import numpy as np

np.random.seed(42)
n = 500
df = pd.DataFrame({
    'Order Date':    pd.date_range('2022-01-01', periods=n, freq='D').astype(str),
    'Ship Mode':     np.random.choice(['First Class', 'Second Class', 'Standard Class'], n),
    'Customer ID':   [f'CU-{i%100}' for i in range(n)],
    'Segment':       np.random.choice(['Consumer', 'Corporate', 'Home Office'], n),
    'Country':       'United States',
    'Region':        np.random.choice(['East', 'West', 'Central', 'South'], n),
    'Category':      np.random.choice(['Furniture', 'Office Supplies', 'Technology'], n),
    'Sub-Category':  np.random.choice(['Chairs', 'Binders', 'Phones'], n),
    'Sales':         np.random.uniform(10, 5000, n),
    'Quantity':      np.random.randint(1, 10, n),
    'Discount':      np.random.uniform(0, 0.5, n),
    'Profit':        np.random.uniform(-200, 1000, n),
    'Row ID':        range(1, n+1),
})

print("DF shape:", df.shape)
print("Columns:", df.columns.tolist())

from app.services.revenue_engine import _try_compute_revenue, detect_revenue_column, detect_date_column
df2 = _try_compute_revenue(df)
rev_col = detect_revenue_column(df2)
date_col = detect_date_column(df2)
print("Revenue col:", rev_col)
print("Date col:  ", date_col)

from app.services.root_cause_analysis import analyze_root_causes
try:
    result = analyze_root_causes(df2, rev_col)
    print("RCA SUCCESS")
    print("  status       :", result.get('current_period'))
    print("  change_pct   :", result.get('change_percent'))
    print("  top_drivers  :", len(result.get('top_drivers', [])))
    print("  insight      :", result.get('insight_summary', '')[:100])
except Exception as e:
    print("RCA FAILED:")
    traceback.print_exc()
