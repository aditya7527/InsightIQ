"""
Root Cause Analysis Engine
Identifies key revenue drivers using month-over-month comparison.
Returns structured output — never returns "undefined".
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# ID columns to exclude from analysis
ID_PATTERNS = ['id', 'no', 'code', 'key', 'uuid', 'index', 'invoiceno', 'stockcode', 'customerid']


def _is_id(col: str) -> bool:
    cleaned = col.lower().replace('_', '').replace(' ', '')
    return any(p in cleaned for p in ID_PATTERNS)


def _find_col(df, patterns):
    for col in df.columns:
        cleaned = col.lower().replace('_', '').replace(' ', '')
        for p in patterns:
            if cleaned == p.replace('_', ''):
                return col
    return None


def analyze_root_causes(
    df: pd.DataFrame,
    metric_col: str,
    group_cols: Optional[List[str]] = None,
    compare_periods: bool = True
) -> Dict:
    """
    Analyze root causes of metric changes using month-over-month comparison.
    Returns structured drivers with 'driver' key — never 'undefined'.
    """
    try:
        # ── Step 0: Compute Revenue if needed ──
        qty_col = _find_col(df, ['quantity', 'qty'])
        price_col = _find_col(df, ['unitprice', 'unit_price', 'price'])
        if metric_col not in df.columns and qty_col and price_col:
            df = df.copy()
            df['Revenue'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) * \
                            pd.to_numeric(df[price_col], errors='coerce').fillna(0)
            metric_col = 'Revenue'

        if metric_col not in df.columns:
            return _safe_response(metric_col, error='Column not found')

        # ── Step 1: Detect date column ──
        date_col = None
        for col in df.columns:
            if any(kw in col.lower() for kw in ['date', 'time', 'day', 'period']):
                date_col = col
                break

        # ── Step 2: Try month-over-month analysis ──
        if date_col:
            try:
                ts = df.copy()
                ts['_dt'] = pd.to_datetime(ts[date_col], errors='coerce')
                ts = ts.dropna(subset=['_dt'])
                ts['_month'] = ts['_dt'].dt.to_period('M')
                months = ts['_month'].unique()
                months = sorted(months)

                if len(months) >= 2:
                    latest = months[-1]
                    previous = months[-2]
                    df_latest = ts[ts['_month'] == latest]
                    df_previous = ts[ts['_month'] == previous]

                    total_latest = df_latest[metric_col].sum()
                    total_previous = df_previous[metric_col].sum()
                    total_change = total_latest - total_previous

                    drivers = []

                    # ── Driver 1: Country breakdown ──
                    country_col = _find_col(df, ['country', 'region', 'state', 'territory', 'area'])
                    if country_col and country_col in df.columns:
                        drivers += _compare_by_group(
                            df_latest, df_previous, metric_col, country_col, total_change
                        )

                    # ── Driver 2: Product breakdown ──
                    product_col = _find_col(df, ['description', 'product', 'item', 'category', 'productcategory'])
                    if product_col and product_col in df.columns:
                        drivers += _compare_by_group(
                            df_latest, df_previous, metric_col, product_col, total_change, top_n=10
                        )

                    # ── Driver 3: Returns impact ──
                    if qty_col and qty_col in df.columns:
                        returns_latest = df_latest[pd.to_numeric(df_latest[qty_col], errors='coerce') < 0][metric_col].sum()
                        returns_prev = df_previous[pd.to_numeric(df_previous[qty_col], errors='coerce') < 0][metric_col].sum()
                        returns_change = abs(returns_latest) - abs(returns_prev)
                        if total_change != 0 and returns_change != 0:
                            impact = (returns_change / abs(total_change)) * 100
                            drivers.append({
                                'driver': 'Returns Impact',
                                'contribution_percent': round(abs(impact), 1),
                                'group_name': f'Returns changed by ${abs(returns_change):,.0f}',
                                'direction': 'negative' if returns_change > 0 else 'positive'
                            })

                    # ── Driver 4: UnitPrice variance ──
                    if price_col and price_col in df.columns:
                        avg_price_latest = pd.to_numeric(df_latest[price_col], errors='coerce').mean()
                        avg_price_prev = pd.to_numeric(df_previous[price_col], errors='coerce').mean()
                        if avg_price_prev > 0:
                            price_change_pct = ((avg_price_latest - avg_price_prev) / avg_price_prev) * 100
                            if abs(price_change_pct) > 1:
                                drivers.append({
                                    'driver': 'Unit Price Variance',
                                    'contribution_percent': round(abs(price_change_pct), 1),
                                    'group_name': f'Avg price {"increased" if price_change_pct > 0 else "decreased"} by {abs(price_change_pct):.1f}%',
                                    'direction': 'positive' if price_change_pct > 0 else 'negative'
                                })

                    # Sort by impact and take top 5
                    drivers = sorted(drivers, key=lambda x: x.get('contribution_percent', 0), reverse=True)[:5]

                    # Generate insight summary
                    primary = drivers[0] if drivers else None
                    if total_previous > 0:
                        rev_change_pct = ((total_latest - total_previous) / abs(total_previous)) * 100
                    else:
                        rev_change_pct = 0

                    insight = (
                        f"Revenue {'increased' if total_change >= 0 else 'decreased'} by "
                        f"${abs(total_change):,.0f} ({rev_change_pct:+.1f}%) from {previous} to {latest}."
                    )
                    if primary:
                        insight += f" Primary driver: {primary['driver']} ({primary['contribution_percent']:.1f}% impact)."

                    return {
                        'metric': metric_col,
                        'current_value': float(total_latest),
                        'previous_value': float(total_previous),
                        'kpi_change_percent': round(rev_change_pct, 1),
                        'top_drivers': drivers,
                        'total_insights': len(drivers),
                        'insight_summary': insight,
                        'recommendations': _generate_recommendations(drivers, rev_change_pct),
                        'period': {'latest': str(latest), 'previous': str(previous)}
                    }
            except Exception as e:
                logger.warning(f"MoM analysis failed, falling back: {e}")

        # ── Fallback: Static group analysis (no time data) ──
        return _static_group_analysis(df, metric_col, group_cols)

    except Exception as e:
        logger.error(f"Root cause error: {e}")
        return _safe_response(metric_col, error=str(e))


def _compare_by_group(
    df_latest: pd.DataFrame,
    df_prev: pd.DataFrame,
    metric_col: str,
    group_col: str,
    total_change: float,
    top_n: int = 5
) -> List[Dict]:
    """Compare a grouping column between two periods."""
    drivers = []
    try:
        latest_by = df_latest.groupby(group_col)[metric_col].sum()
        prev_by = df_prev.groupby(group_col)[metric_col].sum()
        all_groups = set(latest_by.index) | set(prev_by.index)

        changes = []
        for g in all_groups:
            cur = latest_by.get(g, 0)
            prev = prev_by.get(g, 0)
            change = cur - prev
            changes.append((g, change, cur))

        changes.sort(key=lambda x: abs(x[1]), reverse=True)

        for group_name, change, current in changes[:top_n]:
            if total_change != 0 and change != 0:
                impact = (change / abs(total_change)) * 100
                total_rev = df_latest[metric_col].sum()
                contribution = (current / total_rev * 100) if total_rev > 0 else 0

                drivers.append({
                    'driver': f"{group_col}: {group_name}",
                    'contribution_percent': round(abs(impact), 1),
                    'group_name': (
                        f"{group_name} contributes {contribution:.0f}% of total revenue"
                    ),
                    'direction': 'positive' if change > 0 else 'negative'
                })
    except Exception:
        pass
    return drivers


def _static_group_analysis(df, metric_col, group_cols):
    """Fallback analysis when no time data is available."""
    total = df[metric_col].sum()
    if total == 0:
        return _safe_response(metric_col, error='Metric total is zero')

    drivers = []
    if group_cols:
        for gc in group_cols:
            if gc in df.columns and not _is_id(gc):
                grouped = df.groupby(gc)[metric_col].sum().sort_values(ascending=False).head(5)
                for name, val in grouped.items():
                    contribution = (val / total) * 100 if total > 0 else 0
                    drivers.append({
                        'driver': f"{gc}: {name}",
                        'contribution_percent': round(contribution, 1),
                        'group_name': f"{name} contributes {contribution:.0f}% of total",
                        'direction': 'positive'
                    })

    drivers = sorted(drivers, key=lambda x: x['contribution_percent'], reverse=True)[:5]

    return {
        'metric': metric_col,
        'current_value': float(total),
        'top_drivers': drivers,
        'total_insights': len(drivers),
        'insight_summary': f"Static analysis: Top drivers ranked by contribution to {metric_col}.",
        'recommendations': _generate_recommendations(drivers, 0)
    }


def _safe_response(metric_col: str, error: str = '') -> Dict:
    """Return a safe, never-undefined response."""
    msg = error or 'Not enough time-series data for root cause analysis.'
    return {
        'metric': metric_col,
        'current_value': 0,
        'top_drivers': [],
        'total_insights': 0,
        'insight_summary': msg,
        'recommendations': ['Ensure the dataset has date and numeric columns for analysis.']
    }


def _generate_recommendations(drivers: List[Dict], change_pct: float) -> List[str]:
    """Generate actionable recommendations."""
    recs = []
    for d in drivers[:3]:
        name = d.get('driver', 'Unknown')
        pct = d.get('contribution_percent', 0)
        direction = d.get('direction', 'positive')

        if pct > 20:
            recs.append(f"Focus on {name} — accounts for {pct:.1f}% of change")
        elif direction == 'negative':
            recs.append(f"Investigate decline in {name}")
        else:
            recs.append(f"Monitor {name} ({pct:.1f}% impact)")

    if change_pct < -5:
        recs.append("Revenue declining — review pricing strategy and customer retention")
    elif change_pct > 10:
        recs.append("Strong growth — consider scaling operations to sustain momentum")

    if not recs:
        recs.append("No significant drivers detected — review data quality")

    return recs


def detect_anomalies(df: pd.DataFrame, metric_col: str) -> List[Dict]:
    """Detect anomalies in metric using statistical methods."""
    anomalies = []
    try:
        data = df[metric_col].dropna()
        if len(data) < 3:
            return anomalies

        mean = data.mean()
        std = data.std()
        if std == 0:
            return anomalies

        outliers = data[(data > mean + 2 * std) | (data < mean - 2 * std)]
        for idx, value in outliers.head(10).items():
            deviation = (value - mean) / std
            anomalies.append({
                'index': int(idx),
                'value': float(value),
                'mean': float(mean),
                'deviation_sigma': round(deviation, 2),
                'severity': 'High' if abs(deviation) > 3 else 'Medium'
            })
    except Exception as e:
        logger.warning(f"Anomaly detection: {e}")

    return anomalies
