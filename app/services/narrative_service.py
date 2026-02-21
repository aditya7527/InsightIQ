
from typing import Dict, List, Optional

def generate_summary(forecast_data: Dict, root_cause_data: Dict) -> Dict:
    """
    Generate deterministic narratives based on strict rules.
    No LLM hallucinations.
    """
    narratives = {
        "summary": "",
        "trend_narrative": "",
        "risk_alert": "",
        "driver_narrative": ""
    }
    
    # ── 1. Forecast Narrative ──
    trend = forecast_data.get("trend", "stable")
    metrics = forecast_data.get("metrics", {})
    reliability = metrics.get("reliability", "medium")
    
    if trend == "increasing":
        narratives["trend_narrative"] = "Revenue is projected to grow over the coming periods."
    elif trend == "decreasing":
        narratives["trend_narrative"] = "Revenue is projected to decline."
    else:
        narratives["trend_narrative"] = "Revenue is expected to remain stable."
        
    if reliability == "low":
        narratives["trend_narrative"] += " Note: Forecast confidence is limited due to historical volatility."

    # ── 2. Risk Alerts ──
    # Check for significant forecast decline or root cause decline
    f_values = [item['value'] for item in forecast_data.get('forecast', [])]
    if f_values and len(f_values) >= 2:
        start = f_values[0]
        end = f_values[-1]
        if start > 0:
            change = (end - start) / start
            if change < -0.10:
                narratives["risk_alert"] = "[RISK] Significant revenue decline (>10%) detected in forecast."

    # ── 3. Root Cause Narrative ──
    drivers = root_cause_data.get("top_drivers", [])
    change_pct = root_cause_data.get("kpi_change_percent", 0)
    
    if abs(change_pct) < 5:
        narratives["driver_narrative"] = "No significant deviation in revenue detected."
    else:
        # Find primary driver
        primary = None
        for d in drivers:
            if d.get("normalized_percent", 0) > 40:
                primary = d
                break
        
        if primary:
            direction = "growth" if primary.get("direction") == "positive" else "decline"
            narratives["driver_narrative"] = f"Primary driver of {direction} is {primary.get('name', 'Unknown')} ({primary.get('normalized_percent'):.1f}% contribution)."
        elif drivers:
            top = drivers[0]
            narratives["driver_narrative"] = f"Top factor: {top.get('name', 'Unknown')} ({top.get('normalized_percent'):.1f}% contribution)."

    # ── 4. Construct Executive Summary ──
    parts = [narratives["trend_narrative"], narratives["risk_alert"], narratives["driver_narrative"]]
    narratives["summary"] = " ".join([p for p in parts if p])
    
    return narratives
