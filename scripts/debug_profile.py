"""Isolated test: profile_dataset on a Superstore-like dataframe."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

# Simulate Superstore dataset columns
np.random.seed(42)
n = 500
df = pd.DataFrame({
    'Order ID':      [f'CA-{i}' for i in range(n)],
    'Order Date':    pd.date_range('2022-01-01', periods=n, freq='D'),
    'Ship Date':     pd.date_range('2022-01-03', periods=n, freq='D'),
    'Ship Mode':     np.random.choice(['First Class', 'Second Class', 'Standard Class'], n),
    'Customer ID':   [f'CU-{i%100}' for i in range(n)],
    'Segment':       np.random.choice(['Consumer', 'Corporate', 'Home Office'], n),
    'Country':       'United States',
    'City':          np.random.choice(['New York', 'Los Angeles', 'Chicago'], n),
    'State':         np.random.choice(['New York', 'California', 'Illinois'], n),
    'Region':        np.random.choice(['East', 'West', 'Central', 'South'], n),
    'Product ID':    [f'FUR-{i%200}' for i in range(n)],
    'Category':      np.random.choice(['Furniture', 'Office Supplies', 'Technology'], n),
    'Sub-Category':  np.random.choice(['Chairs', 'Binders', 'Phones'], n),
    'Product Name':  [f'Product {i%50}' for i in range(n)],
    'Sales':         np.random.uniform(10, 5000, n),
    'Quantity':      np.random.randint(1, 10, n),
    'Discount':      np.random.uniform(0, 0.5, n),
    'Profit':        np.random.uniform(-200, 1000, n),
    'Row ID':        range(1, n+1),
})

print(f"Test DataFrame: {df.shape}")

from app.services.revenue_engine import _try_compute_revenue
df2 = _try_compute_revenue(df)
print("Revenue col after _try_compute:", 'Revenue' in df2.columns)
print("Cols:", [c for c in df2.columns if not c.startswith('Row')])

from app.services.profiling import profile_dataset
try:
    profile = profile_dataset(df2)
    print("profile_dataset: SUCCESS")
    metrics = [(m['label'], round(m['value'], 2)) for m in profile.get('computed_metrics', [])]
    print("Computed metrics:", metrics)
    print("Time series:", profile.get('time_series') is not None)
    print("Top countries:", profile.get('top_countries') is not None)
except Exception as e:
    print("profile_dataset FAILED:")
    traceback.print_exc()
