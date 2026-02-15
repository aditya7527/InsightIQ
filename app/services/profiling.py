"""
Dataset Profiling Engine
Generates comprehensive analytics profile with smart KPI detection,
Revenue computation, ID column exclusion, and derived business metrics.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Set

# Columns that should NEVER be treated as numeric metrics even if they have numeric dtype
ID_COLUMN_PATTERNS = [
    'id', 'no', 'code', 'key', 'index', 'uuid', 'guid',
    'invoiceno', 'stockcode', 'customerid', 'productid',
    'orderid', 'transactionid', 'employeeid', 'zipcode', 'postal'
]


def _is_id_column(col_name: str) -> bool:
    """Check if a column is an ID/code column that should be excluded from numeric analysis."""
    cleaned = col_name.lower().replace('_', '').replace(' ', '').replace('-', '')
    return any(pattern in cleaned for pattern in ID_COLUMN_PATTERNS)


def _detect_date_col(df: pd.DataFrame) -> str | None:
    """Auto-detect the best date column."""
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ['date', 'time', 'day', 'month', 'year', 'period']):
            return col
    for col in df.select_dtypes(include=['object']).columns:
        try:
            sample = df[col].dropna().head(5)
            pd.to_datetime(sample)
            return col
        except Exception:
            continue
    return None


def _compute_mom_growth(monthly_rev: pd.Series) -> float | None:
    """Compute Month-over-Month growth % from last two months."""
    if len(monthly_rev) < 2:
        return None
    last = monthly_rev.iloc[-1]
    prev = monthly_rev.iloc[-2]
    if prev == 0:
        return None
    return round(((last - prev) / abs(prev)) * 100, 1)


def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate a comprehensive profile of the dataset with smart KPIs."""
    total_rows = len(df)
    total_cols = len(df.columns)

    profile = {
        'total_rows': total_rows,
        'total_columns': total_cols,
        'column_stats': {},
        'numeric_summary': [],
        'categorical_summary': [],
        'date_ranges': {},
        'computed_metrics': [],
        'category_distributions': {},
        'time_series': None,
        'correlation_pairs': [],
        'top_countries': None,
        'revenue_by_month': None,
    }

    # ── Step 1: Compute Revenue if Quantity and UnitPrice exist ──
    has_quantity = _find_col(df, ['quantity', 'qty', 'units_sold'])
    has_price = _find_col(df, ['unitprice', 'unit_price', 'price', 'unit price'])
    revenue_col_name = None

    if has_quantity and has_price:
        df = df.copy()
        df['Revenue'] = pd.to_numeric(df[has_quantity], errors='coerce').fillna(0) * \
                        pd.to_numeric(df[has_price], errors='coerce').fillna(0)
        revenue_col_name = 'Revenue'

    # ── Step 2: Detect date column ──
    date_col = _detect_date_col(df)
    date_series = None
    if date_col:
        date_series = pd.to_datetime(df[date_col], errors='coerce')

    # ── Step 3: Column Statistics ──
    for col in df.columns:
        non_null = int(df[col].count())
        missing = total_rows - non_null
        missing_pct = (missing / total_rows) * 100 if total_rows > 0 else 0
        dtype_str = str(df[col].dtype)

        profile['column_stats'][col] = {
            'dtype': dtype_str,
            'non_null_count': non_null,
            'missing_count': int(missing),
            'missing_percent': round(missing_pct, 2),
            'unique_values': int(df[col].nunique()),
            'is_id': _is_id_column(col)
        }

    # ── Step 4: Numeric Summary (excluding ID columns) ──
    numeric_cols = df.select_dtypes(include=['number']).columns
    analysis_numeric = [c for c in numeric_cols if not _is_id_column(c)]

    for col in analysis_numeric:
        try:
            col_sum = float(df[col].sum())
            stats = {
                'name': col,
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'mean': float(df[col].mean()),
                'std': float(df[col].std()) if pd.notna(df[col].std()) else 0.0,
                'median': float(df[col].median()),
                'sum': col_sum
            }
            profile['numeric_summary'].append(stats)
        except Exception:
            continue

    # ── Step 5: Smart Computed Metrics ──
    # 5a. Revenue (computed or detected)
    if revenue_col_name and revenue_col_name in df.columns:
        positive_rev = df.loc[df['Revenue'] > 0, 'Revenue'].sum()
        total_rev = float(df['Revenue'].sum())

        # MoM growth
        mom_growth = None
        if date_series is not None:
            try:
                ts_df = df.copy()
                ts_df['_month'] = date_series.dt.to_period('M')
                monthly = ts_df.groupby('_month')['Revenue'].sum().sort_index()
                mom_growth = _compute_mom_growth(monthly)
            except Exception:
                pass

        profile['computed_metrics'].append({
            'label': 'Total Revenue',
            'value': float(positive_rev),
            'column': 'Revenue',
            'icon': 'dollar',
            'format': 'currency',
            'change_pct': mom_growth
        })

        # 5b. Average Order Value
        invoice_col = _find_col(df, ['invoiceno', 'invoice_no', 'orderid', 'order_id', 'transactionid'])
        if invoice_col:
            unique_orders = df[invoice_col].nunique()
            if unique_orders > 0:
                aov = positive_rev / unique_orders
                profile['computed_metrics'].append({
                    'label': 'Avg Order Value',
                    'value': float(aov),
                    'column': 'derived',
                    'icon': 'chart',
                    'format': 'currency',
                    'change_pct': None
                })

        # 5c. Revenue per Customer
        customer_col = _find_col(df, ['customerid', 'customer_id', 'customer', 'client'])
        if customer_col:
            unique_customers = df[customer_col].dropna().nunique()
            if unique_customers > 0:
                rpc = positive_rev / unique_customers
                profile['computed_metrics'].append({
                    'label': 'Revenue / Customer',
                    'value': float(rpc),
                    'column': 'derived',
                    'icon': 'dollar',
                    'format': 'currency',
                    'change_pct': None
                })
                # Active Customers metric
                profile['computed_metrics'].append({
                    'label': 'Active Customers',
                    'value': int(unique_customers),
                    'column': customer_col,
                    'icon': 'users',
                    'format': 'integer',
                    'change_pct': None
                })

        # 5d. Return Rate
        negative_rev = float(df.loc[df['Revenue'] < 0, 'Revenue'].sum())
        if positive_rev > 0 and negative_rev < 0:
            return_rate = (abs(negative_rev) / positive_rev) * 100
            profile['computed_metrics'].append({
                'label': 'Return Rate',
                'value': round(return_rate, 1),
                'column': 'derived',
                'icon': 'returns',
                'format': 'percent',
                'change_pct': None
            })
    else:
        # Fallback: detect revenue-like and quantity-like columns individually
        # Quantity-like keywords to EXCLUDE from revenue detection
        qty_keywords = ['quantity', 'qty', 'units', 'unit', 'count', 'items']
        revenue_added = False
        for col in analysis_numeric:
            col_lower = col.lower()
            col_sum = float(df[col].sum())

            # Skip columns that look like quantity/units — they are NOT revenue
            if any(kw in col_lower for kw in qty_keywords):
                continue

            if not revenue_added and any(kw in col_lower for kw in ['revenue', 'sales', 'amount', 'total', 'income']):
                profile['computed_metrics'].append({
                    'label': 'Total Revenue',
                    'value': col_sum,
                    'column': col,
                    'icon': 'dollar',
                    'format': 'currency',
                    'change_pct': _compute_change(df, col)
                })
                revenue_added = True
            elif any(kw in col_lower for kw in ['profit', 'margin', 'net', 'earning']):
                profile['computed_metrics'].append({
                    'label': 'Net Profit',
                    'value': col_sum,
                    'column': col,
                    'icon': 'chart',
                    'format': 'currency',
                    'change_pct': _compute_change(df, col)
                })

    # 5e. Units Sold (always detect Quantity)
    if has_quantity:
        qty_sum = float(pd.to_numeric(df[has_quantity], errors='coerce').fillna(0).sum())
        # Avoid duplicate: only add if not already present as a metric
        existing_labels = {m['label'] for m in profile['computed_metrics']}
        if 'Units Sold' not in existing_labels:
            profile['computed_metrics'].append({
                'label': 'Units Sold',
                'value': qty_sum,
                'column': has_quantity,
                'icon': 'box',
                'format': 'integer',  # ← NO currency formatting
                'change_pct': _compute_change(df, has_quantity) if has_quantity in df.columns else None
            })

    # ── Step 6: Categorical Summary + Distributions ──
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in cat_cols:
        try:
            vc = df[col].value_counts().head(10)
            profile['categorical_summary'].append({
                'name': col,
                'unique_values': int(df[col].nunique()),
                'top_value': str(vc.index[0]) if len(vc) > 0 else '',
                'top_count': int(vc.iloc[0]) if len(vc) > 0 else 0
            })
            profile['category_distributions'][col] = {
                'labels': [str(x) for x in vc.index.tolist()],
                'values': [int(x) for x in vc.values.tolist()]
            }
        except Exception:
            continue

    # ── Step 7: Time Series — Monthly Revenue ──
    val_col_for_ts = revenue_col_name or _find_revenue_col(df, analysis_numeric)
    if date_series is not None and val_col_for_ts and val_col_for_ts in df.columns:
        try:
            ts_df = df.copy()
            ts_df['_dt'] = date_series
            ts_df = ts_df.dropna(subset=['_dt']).sort_values('_dt')
            ts_df['_month'] = ts_df['_dt'].dt.to_period('M')

            monthly = ts_df.groupby('_month')[val_col_for_ts].sum().reset_index()
            monthly.columns = ['month', 'value']
            monthly['month_str'] = monthly['month'].astype(str)

            profile['time_series'] = {
                'date_column': date_col,
                'value_column': val_col_for_ts,
                'dates': monthly['month_str'].tolist(),
                'values': [float(v) for v in monthly['value'].tolist()],
                'aggregation': 'monthly'
            }

            profile['revenue_by_month'] = {
                'labels': monthly['month_str'].tolist(),
                'values': [float(v) for v in monthly['value'].tolist()]
            }
        except Exception:
            pass

    # ── Step 8: Top Countries by Revenue ──
    country_col = _find_col(df, ['country', 'region', 'state', 'territory', 'area', 'zone'])
    if country_col and val_col_for_ts and val_col_for_ts in df.columns:
        try:
            by_country = df.groupby(country_col)[val_col_for_ts].sum().sort_values(ascending=False).head(5)
            profile['top_countries'] = {
                'column': country_col,
                'labels': [str(x) for x in by_country.index.tolist()],
                'values': [float(v) for v in by_country.values.tolist()]
            }
        except Exception:
            pass

    # ── Step 9: Correlation — Revenue vs Quantity (not IDs) ──
    if date_series is not None and revenue_col_name and has_quantity:
        try:
            ts_df = df.copy()
            ts_df['_dt'] = date_series
            ts_df = ts_df.dropna(subset=['_dt']).sort_values('_dt')
            ts_df['_month'] = ts_df['_dt'].dt.to_period('M')

            corr_df = ts_df.groupby('_month').agg({
                revenue_col_name: 'sum',
                has_quantity: 'sum'
            }).reset_index()
            corr_df['month_str'] = corr_df['_month'].astype(str)

            profile['correlation_pairs'] = [{
                'col1': revenue_col_name,
                'col2': has_quantity,
                'dates': corr_df['month_str'].tolist(),
                'values1': [float(v) for v in corr_df[revenue_col_name].tolist()],
                'values2': [float(v) for v in corr_df[has_quantity].tolist()]
            }]
        except Exception:
            pass

    # ── Step 10: Date Ranges ──
    if date_col:
        try:
            if date_series is not None:
                valid = date_series.dropna()
                if not valid.empty:
                    profile['date_ranges'][date_col] = {
                        'start': str(valid.min().date()),
                        'end': str(valid.max().date())
                    }
        except Exception:
            pass

    return profile


# ── Helper Functions ──

def _find_col(df: pd.DataFrame, patterns: list) -> str | None:
    """Find a column matching any of the given patterns (case-insensitive)."""
    for col in df.columns:
        cleaned = col.lower().replace('_', '').replace(' ', '')
        for pattern in patterns:
            if cleaned == pattern.replace('_', ''):
                return col
    return None


def _find_revenue_col(df: pd.DataFrame, numeric_cols: list) -> str | None:
    """Find the best revenue-like column from numeric columns."""
    for col in numeric_cols:
        if any(kw in col.lower() for kw in ['revenue', 'sales', 'amount', 'total', 'income']):
            return col
    return numeric_cols[0] if numeric_cols else None


def _compute_change(df, col):
    """Compute approximate period-over-period % change."""
    try:
        n = len(df)
        if n < 4:
            return None
        half = n // 2
        first_half = df[col].iloc[:half].sum()
        second_half = df[col].iloc[half:].sum()
        if first_half == 0:
            return None
        change = ((second_half - first_half) / abs(first_half)) * 100
        return round(change, 1)
    except Exception:
        return None
