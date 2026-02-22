import pandas as pd
from typing import Dict

def compute_revenue_bridge(monthly_series: pd.Series, df: pd.DataFrame, revenue_col: str, date_col: str) -> Dict:
    """
    Compute Month-over-Month Revenue Bridge.
    Decomposes the delta between the last two months by analyzing top 5 categorical drivers.
    Returns:
    {
      "previous_value": float,
      "components": [{"label": str, "value": float, "direction": "positive"|"negative", "normalized_percent": float}],
      "current_value": float
    }
    """
    # Step 1: Identify Periods
    if len(monthly_series) < 2:
        return {"previous_value": 0.0, "components": [], "current_value": 0.0}

    current_month = monthly_series.index[-1]
    previous_month = monthly_series.index[-2]

    # Step 2: Compute Revenue Delta
    previous_value = float(monthly_series.iloc[-2])
    current_value = float(monthly_series.iloc[-1])
    
    # Step 3: Dimension Contribution
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col, revenue_col])
    
    # Exclude ids/dates/revenue
    def _is_id(c):
        cl = c.lower().replace('_', '').replace(' ', '')
        return any(p in cl for p in ['id', 'no', 'code', 'key', 'uuid', 'index'])
        
    categorical_cols = [
        c for c in df.columns 
        if c not in {date_col, revenue_col}
        and not _is_id(c)
        and str(df[c].dtype) in ('object', 'category', 'string')
        and df[c].nunique() <= 50
    ]
    
    components = []
    
    for dimension in categorical_cols:
        grouped = df.groupby([dimension, pd.Grouper(key=date_col, freq="MS")])[revenue_col].sum()
        try:
            pivot = grouped.unstack(fill_value=0)
            
            # Make sure we have both months in the pivot (index matching)
            # pivot columns might be actual pd.Timestamp objects
            # get current and previous months if they exist in pivot
            if current_month not in pivot.columns or previous_month not in pivot.columns:
                continue
                
            delta = pivot[current_month] - pivot[previous_month]
            
            for label, val in delta.items():
                if pd.isna(label) or label == "":
                    continue
                if abs(val) > 0.01:
                    components.append({
                        "dimension": dimension,
                        "label": str(label),
                        "delta": float(val)
                    })
        except Exception:
            continue
            
    # Rank by absolute delta
    components.sort(key=lambda x: abs(x["delta"]), reverse=True)
    
    # Take Top 5 contributors
    top_components = components[:5]
    
    # Normalize
    abs_total = sum(abs(c["delta"]) for c in top_components)
    
    final_components = []
    for c in top_components:
        normalized_percent = (abs(c["delta"]) / abs_total * 100) if abs_total > 0 else 0.0
        final_components.append({
            "label": f"{c['dimension']}: {c['label']}",
            "value": round(c["delta"], 2),
            "direction": "positive" if c["delta"] > 0 else "negative",
            "normalized_percent": round(normalized_percent, 1)
        })
        
    # Step 4: Return Structured Waterfall Data
    return {
        "previous_value": previous_value,
        "components": final_components,
        "current_value": current_value
    }
