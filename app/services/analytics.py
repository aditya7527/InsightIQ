from typing import Dict, Any
from sqlalchemy import text


def generate_sql(template_name: str, table_name: str) -> str:
    templates = {
        "revenue_trends": f"SELECT date_trunc('month', sale_date) AS month, SUM(revenue) AS revenue FROM {table_name} GROUP BY month ORDER BY month",
        "sales_growth": f"SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) as prev, (revenue - COALESCE(LAG(revenue) OVER (ORDER BY month), 0)) / NULLIF(COALESCE(LAG(revenue) OVER (ORDER BY month),0),0)::float as growth FROM (SELECT date_trunc('month', sale_date) AS month, SUM(revenue) AS revenue FROM {table_name} GROUP BY month) t",
        "marketing_roi": f"SELECT campaign, SUM(spend) as spend, SUM(revenue) as revenue, CASE WHEN SUM(spend)=0 THEN NULL ELSE SUM(revenue)/SUM(spend) END as roi FROM {table_name} GROUP BY campaign",
        "customer_segmentation": f"SELECT customer_segment, COUNT(*) as customers, SUM(revenue) as revenue FROM {table_name} GROUP BY customer_segment",
    }
    return templates.get(template_name, "")


def run_sql(engine, sql: str):
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = result.keys()
        rows = [dict(zip(cols, r)) for r in result.fetchall()]
    return rows
