"""
Forecasting Module
Monthly revenue forecasting using linear regression.
Returns historical + forecast + confidence band.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sklearn.linear_model import LinearRegression
import logging

logger = logging.getLogger(__name__)

# ID columns to exclude
ID_PATTERNS = ['id', 'no', 'code', 'key', 'uuid', 'invoiceno', 'stockcode', 'customerid']


def _is_id(col: str) -> bool:
    cleaned = col.lower().replace('_', '').replace(' ', '')
    return any(p in cleaned for p in ID_PATTERNS)


def auto_detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Auto-detect date column in DataFrame."""
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ['date', 'time', 'datetime', 'day', 'month', 'year', 'period']):
            return col
    # Try parsing
    for col in df.select_dtypes(include=['object']).columns:
        try:
            sample = df[col].dropna().head(5)
            pd.to_datetime(sample)
            if pd.to_datetime(df[col], errors='coerce').notna().sum() > len(df) * 0.5:
                return col
        except Exception:
            pass
    return None


def auto_detect_revenue_column(df: pd.DataFrame) -> Optional[str]:
    """Auto-detect revenue column (excludes ID columns)."""
    revenue_keywords = ['revenue', 'sales', 'profit', 'income', 'amount', 'value', 'total']
    for col in df.columns:
        if _is_id(col):
            continue
        col_lower = col.lower()
        if any(kw in col_lower for kw in revenue_keywords):
            if pd.api.types.is_numeric_dtype(df[col]):
                return col
    # Fallback: largest non-ID numeric column
    numeric_cols = [c for c in df.select_dtypes(include=['number']).columns if not _is_id(c)]
    if numeric_cols:
        return df[numeric_cols].mean().idxmax()
    return None


def _find_col(df, patterns):
    for col in df.columns:
        cleaned = col.lower().replace('_', '').replace(' ', '')
        for p in patterns:
            if cleaned == p.replace('_', ''):
                return col
    return None


def forecast_monthly_revenue(df: pd.DataFrame, periods: int = 3) -> Dict:
    """
    Proper monthly revenue forecasting.

    Steps:
    1. Compute Revenue = Quantity × UnitPrice (if needed)
    2. Aggregate to monthly totals
    3. Require ≥ 6 months of data
    4. Linear regression forecast
    5. Return historical + forecast + confidence_band

    Returns:
        Dict with 'historical', 'forecast', 'confidence_band', and metadata.
    """
    try:
        # Step 1: Find or compute Revenue
        qty_col = _find_col(df, ['quantity', 'qty'])
        price_col = _find_col(df, ['unitprice', 'unit_price', 'price'])
        date_col = auto_detect_date_column(df)

        if not date_col:
            return {'error': 'No date column found.', 'forecast': [], 'historical': []}

        df = df.copy()

        # Compute Revenue
        if 'Revenue' not in df.columns and qty_col and price_col:
            df['Revenue'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) * \
                            pd.to_numeric(df[price_col], errors='coerce').fillna(0)

        value_col = 'Revenue' if 'Revenue' in df.columns else auto_detect_revenue_column(df)
        if not value_col or value_col not in df.columns:
            return {'error': 'No revenue column found.', 'forecast': [], 'historical': []}

        # Step 2: Parse dates and aggregate monthly
        df['_dt'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['_dt'])

        if df.empty:
            return {'error': 'No valid dates in dataset.', 'forecast': [], 'historical': []}

        df['_month'] = df['_dt'].dt.to_period('M')
        monthly = df.groupby('_month')[value_col].sum().sort_index().reset_index()
        monthly.columns = ['month', 'revenue']

        # Step 3: Check minimum data requirement
        if len(monthly) < 6:
            # Return historical but no forecast
            historical = [
                {'date': str(row['month']), 'value': float(row['revenue'])}
                for _, row in monthly.iterrows()
            ]
            return {
                'historical': historical,
                'forecast': [],
                'confidence_band': [],
                'date_column': date_col,
                'value_column': value_col,
                'message': f'Insufficient data for forecasting. Need ≥ 6 months, have {len(monthly)}.',
                'method': 'none'
            }

        # Step 4: Linear Regression
        monthly['month_num'] = np.arange(len(monthly))
        X = monthly['month_num'].values.reshape(-1, 1)
        y = monthly['revenue'].values

        model = LinearRegression()
        model.fit(X, y)

        # Calculate residuals for confidence band
        y_pred_train = model.predict(X)
        residuals = y - y_pred_train
        residual_std = float(np.std(residuals))

        # Historical data
        historical = [
            {'date': str(row['month']), 'value': float(row['revenue'])}
            for _, row in monthly.iterrows()
        ]

        # Step 5: Forecast future months
        last_month_num = monthly['month_num'].iloc[-1]
        last_period = monthly['month'].iloc[-1]

        forecast_data = []
        confidence_band = []

        for i in range(1, periods + 1):
            future_num = last_month_num + i
            predicted = float(model.predict([[future_num]])[0])
            predicted = max(0, predicted)  # No negative revenue

            future_period = last_period + i
            date_str = str(future_period)

            forecast_data.append({
                'date': date_str,
                'period': date_str,
                'predicted_value': round(predicted, 2)
            })

            confidence_band.append({
                'date': date_str,
                'lower': round(max(0, predicted - 1.96 * residual_std), 2),
                'upper': round(predicted + 1.96 * residual_std, 2)
            })

        return {
            'success': True,
            'historical': historical,
            'forecast': forecast_data,
            'confidence_band': confidence_band,
            'date_column': date_col,
            'value_column': value_col,
            'periods': periods,
            'method': 'linear_regression',
            'r_squared': round(float(model.score(X, y)), 4)
        }

    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return {
            'error': str(e),
            'forecast': [],
            'historical': [],
            'confidence_band': []
        }


# ── Legacy functions (kept for backward compatibility in ai.py) ──

def forecast_linear(df, date_col, value_col, periods=6):
    """Legacy wrapper — delegates to monthly forecasting."""
    return forecast_monthly_revenue(df, periods).get('forecast', [])


def forecast_exponential_smoothing(df, date_col, value_col, periods=6):
    """Legacy wrapper."""
    return forecast_monthly_revenue(df, periods).get('forecast', [])
