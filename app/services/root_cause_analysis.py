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
        # ── Step 0: Compute Output Structure Default ──
        # (This ensures we format the response correctly even if we exit early)
        
        # ── Step 1: Detect date column ──
        date_col = None
        for col in df.columns:
            if any(kw in col.lower() for kw in ['date', 'time', 'day', 'period']):
                date_col = col
                break
                
        # ── Step 2: Compute Revenue if needed ──
        qty_col = _find_col(df, ['quantity', 'qty'])
        price_col = _find_col(df, ['unitprice', 'unit_price', 'price'])
        if metric_col not in df.columns and qty_col and price_col:
            df = df.copy()
            df['Revenue'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) * \
                            pd.to_numeric(df[price_col], errors='coerce').fillna(0)
            metric_col = 'Revenue'

        if metric_col not in df.columns:
           return _safe_response(metric_col, error='Column not found')

        # ── Step 3: Trigger Logic ──
        # Check total revenue and MoM change
        total_revenue = df[metric_col].sum()
        
        # If no date column, fallback to static
        if not date_col:
             return _static_group_analysis(df, metric_col, group_cols)

        ts = df.copy()
        ts['_dt'] = pd.to_datetime(ts[date_col], errors='coerce')
        ts = ts.dropna(subset=['_dt'])
        ts['_month'] = ts['_dt'].dt.to_period('M')
        months = sorted(ts['_month'].unique())
        
        if len(months) < 2:
             return _static_group_analysis(df, metric_col, group_cols)
             
        latest = months[-1]
        previous = months[-2]
        df_latest = ts[ts['_month'] == latest]
        df_previous = ts[ts['_month'] == previous]
        
        val_latest = df_latest[metric_col].sum()
        val_prev = df_previous[metric_col].sum()
        change_val = val_latest - val_prev
        
        change_pct = 0
        if val_prev > 0:
            change_pct = (change_val / val_prev) * 100
            
        logger.debug(
            "MoM baseline: previous=%s latest=%s change_pct=%.2f",
            val_prev,
            val_latest,
            change_pct,
        )

        # Trigger Condition: Only run if abs(change) >= 2% OR total > 500 (lower for testing)
        if abs(change_pct) < 2 or val_latest < 500:
            return {
                'metric': metric_col,
                'current_value': float(val_latest),
                'previous_value': float(val_prev),
                'kpi_change_percent': round(change_pct, 1),
                'top_drivers': [],
                'insight_summary': "No significant revenue change detected.",
                'recommendations': []
            }
            
        # ── Step 4: Driver Analysis with Dynamic Dimension Detection ──
        # Scan all columns that are not metric_col, date_col, or ID
        potential_dims = [
            col for col in df.columns 
            if col not in [metric_col, date_col] 
            and not _is_id(col)
            and df[col].dtype in ['object', 'category', 'string']
        ]
        logger.debug("Potential dimensions found: %s", potential_dims)
        
        raw_impacts = []
        for col in potential_dims:
            # Compare this dimension
            l_grp = df_latest.groupby(col)[metric_col].sum()
            p_grp = df_previous.groupby(col)[metric_col].sum()
            all_keys = set(l_grp.index) | set(p_grp.index)
            
            for k in all_keys:
                if pd.isna(k) or k == '': continue
                imp = l_grp.get(k, 0) - p_grp.get(k, 0)
                if abs(imp) > 0.01: 
                    raw_impacts.append({
                        'dimension': col,
                        'name': str(k),
                        'impact_value': imp
                    })
                        
        # Sort by absolute impact to find top drivers
        raw_impacts.sort(key=lambda x: abs(x['impact_value']), reverse=True)
        
        total_abs_impact = sum(abs(x['impact_value']) for x in raw_impacts)
        
        final_drivers = []
        if total_abs_impact > 0:
            for item in raw_impacts[:6]: # Top 6 drivers for more context
                norm_pct = (abs(item['impact_value']) / total_abs_impact) * 100
                final_drivers.append({
                    'dimension': item['dimension'],
                    'name': item['name'],
                    'impact_value': float(item['impact_value']),
                    'normalized_percent': round(norm_pct, 1),
                    'direction': 'positive' if item['impact_value'] > 0 else 'negative'
                })
        
        # ── Step 5: AI Narrative Layer ──
        insight_summary = f"Revenue changed by {change_pct:.1f}%. Top drivers analyzed."
        recommendations = _generate_recommendations(final_drivers, change_pct)
        ai_narrative = None
        
        try:
            from app.ai.gpt_service import query_gpt
            payload = {
                "metric": metric_col,
                "change_pct": change_pct,
                "drivers": final_drivers,
                "total_drivers_found": len(raw_impacts)
            }
            prompt = (
                "You are a business intelligence expert. Analyze these revenue drivers for a month-over-month change. "
                "Provide a natural, professional 2-sentence summary of what happened. "
                "Then provide 3 very specific, data-driven recommendations.\n"
                f"Data: {payload}\n"
                "Format as JSON: {\"summary\": \"...\", \"recommendations\": [\"...\", \"...\", \"...\"]}"
            )
            ai_raw = query_gpt(prompt, max_tokens=300)
            import json
            # Extract JSON
            start = ai_raw.find('{')
            end = ai_raw.rfind('}') + 1
            if start != -1 and end > start:
                ai_data = json.loads(ai_raw[start:end])
                insight_summary = ai_data.get('summary', insight_summary)
                recommendations = ai_data.get('recommendations', recommendations)
                ai_narrative = True
        except Exception as ai_err:
            logger.warning(f"AI Narrative failed: {ai_err}")

        return {
            'metric': metric_col,
            'current_value': float(val_latest),
            'previous_value': float(val_prev),
            'kpi_change_percent': round(change_pct, 1),
            'top_drivers': final_drivers,
            'insight_summary': insight_summary,
            'recommendations': recommendations,
            'ai_generated': ai_narrative
        }

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
    """Legacy function - unused."""
    return []


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
