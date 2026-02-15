from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import logging

from app.core.globals import _datasets
from app.services.profiling import profile_dataset
from app.services.confidence_score import calculate_confidence_score
from app.services.industry_detection import detect_industry, get_industry_context
from app.forecasting.models import (
    auto_detect_date_column,
    auto_detect_revenue_column,
    forecast_monthly_revenue,
    forecast_linear,
    forecast_exponential_smoothing
)
from app.services.root_cause_analysis import analyze_root_causes, detect_anomalies
from app.ai.conversational import ask_question
from app.ai.gpt_service import generate_insights_text, query_gpt
from app.services.analytics import run_sql
from app.database import engine

router = APIRouter(tags=["AI Features"])
logger = logging.getLogger(__name__)

# Request Models
class RootCauseRequest(BaseModel):
    table_name: str
    metric_column: Optional[str] = None
    group_by: Optional[List[str]] = None

class ForecastRequest(BaseModel):
    table_name: str
    periods: int = 3
    method: str = "linear"

class AskRequest(BaseModel):
    table_name: str
    question: str


def _get_df(table_name: str) -> pd.DataFrame:
    """Get DataFrame from cache or database."""
    if table_name in _datasets:
        return _datasets[table_name]
    rows = run_sql(engine, f"SELECT * FROM {table_name}")
    df = pd.DataFrame(rows)
    if df.empty:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return df


def _compute_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Revenue = Quantity × UnitPrice if columns exist."""
    df = df.copy()
    qty_col = _find(df, ['quantity', 'qty'])
    price_col = _find(df, ['unitprice', 'unit_price', 'price'])
    if qty_col and price_col and 'Revenue' not in df.columns:
        df['Revenue'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) * \
                        pd.to_numeric(df[price_col], errors='coerce').fillna(0)
    return df


def _find(df, patterns):
    for col in df.columns:
        cleaned = col.lower().replace('_', '').replace(' ', '')
        for p in patterns:
            if cleaned == p.replace('_', ''):
                return col
    return None


# ========== CONFIDENCE SCORE ==========
@router.get("/confidence/{table_name}")
def get_confidence_score(table_name: str):
    try:
        df = _get_df(table_name)
        profile = profile_dataset(df)
        column_stats = profile['column_stats']
        confidence, quality = calculate_confidence_score(df, column_stats)
        return {
            "confidence_score": confidence,
            "confidence_score_quality": quality,
            "table_name": table_name,
            "rows_analyzed": len(df),
            "columns": len(df.columns)
        }
    except Exception as e:
        logger.error(f"Confidence score error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== INDUSTRY DETECTION ==========
@router.get("/industry/{table_name}")
def detect_industry_endpoint(table_name: str):
    try:
        df = _get_df(table_name)
        industry, recommendations = detect_industry(df, df.columns.tolist())
        return {
            "detected_industry": industry,
            "industry_confidence": recommendations.get('confidence', 0),
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Industry detection error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== EXECUTIVE SUMMARY ==========
@router.get("/summary/{table_name}")
def get_summary(table_name: str):
    try:
        df = _get_df(table_name)
        df = _compute_revenue(df)

        industry, _ = detect_industry(df, df.columns.tolist())
        profile = profile_dataset(df)

        # Build computed summary (always works, no GPT needed)
        metrics = profile.get('computed_metrics', [])
        revenue_metric = next((m for m in metrics if m['label'] == 'Total Revenue'), None)
        aov_metric = next((m for m in metrics if 'Order' in m['label']), None)
        customers_metric = next((m for m in metrics if 'Customer' in m['label']), None)

        summary_lines = []
        summary_lines.append(
            f"Dataset contains {len(df):,} records across {len(df.columns)} columns. "
            f"Industry detected: {industry}."
        )
        if revenue_metric:
            rev_val = revenue_metric['value']
            summary_lines.append(
                f"Total Revenue: ${rev_val:,.0f}."
            )
        if aov_metric:
            summary_lines.append(f"Average Order Value: ${aov_metric['value']:,.2f}.")
        if customers_metric:
            summary_lines.append(f"Active Customers: {int(customers_metric['value']):,}.")

        # Try GPT for richer summary
        next_steps = [
            "Review revenue trends by month for seasonality patterns",
            "Analyze top contributing countries/products",
            "Investigate return rate and refund patterns"
        ]

        try:
            prompt = (
                f"You are a Chief Data Officer. Dataset: {len(df)} rows, industry: {industry}. "
                f"Metrics: {[m['label'] + '=' + str(m['value']) for m in metrics[:5]]}. "
                f"Write a 3-sentence Executive Summary. Return JSON: "
                f'{{"summary":"...","next_steps":["...","...","..."]}}'
            )
            import json
            gpt_text = query_gpt(prompt, max_tokens=400)
            start = gpt_text.find('{')
            end = gpt_text.rfind('}') + 1
            if start != -1 and end > start:
                gpt_data = json.loads(gpt_text[start:end])
                return gpt_data
        except Exception:
            pass

        return {
            "summary": " ".join(summary_lines),
            "next_steps": next_steps
        }

    except Exception as e:
        logger.error(f"Summary error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROOT CAUSE ANALYSIS ==========
@router.post("/root-cause")
def analyze_root_cause(request: RootCauseRequest):
    """Analyze root causes of revenue changes — never returns undefined."""
    try:
        df = _get_df(request.table_name)
        df = _compute_revenue(df)

        # Use Revenue as primary metric
        metric_column = 'Revenue' if 'Revenue' in df.columns else request.metric_column
        if not metric_column:
            metric_column = auto_detect_revenue_column(df)
            if not metric_column:
                return {
                    'metric': 'unknown',
                    'top_drivers': [],
                    'insight_summary': 'No numeric metric column found for analysis.',
                    'recommendations': ['Upload a dataset with numeric values.']
                }

        group_cols = request.group_by
        if group_cols:
            group_cols = [c for c in group_cols if c in df.columns]

        analysis = analyze_root_causes(df, metric_column, group_cols)
        anomalies = detect_anomalies(df, metric_column)
        analysis['anomalies'] = anomalies[:5]

        return analysis

    except Exception as e:
        logger.error(f"Root cause error: {e}")
        return {
            'metric': request.metric_column or 'Revenue',
            'top_drivers': [],
            'insight_summary': f'Analysis error: {str(e)}',
            'recommendations': ['Check dataset format and try again.']
        }


# ========== FORECASTING ==========
@router.post("/forecast")
def forecast_endpoint(request: ForecastRequest):
    """Monthly revenue forecast with historical data and confidence bands."""
    try:
        df = _get_df(request.table_name)
        df = _compute_revenue(df)

        result = forecast_monthly_revenue(df, periods=request.periods)

        # Ensure consistent response
        if 'error' in result and result['error']:
            return {
                'success': False,
                'forecast': [],
                'historical': result.get('historical', []),
                'message': result['error']
            }

        return result

    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return {
            'success': False,
            'forecast': [],
            'historical': [],
            'message': str(e)
        }


# ========== ASK YOUR DATA ==========
@router.post("/ask")
async def ask_data_endpoint(request: AskRequest):
    try:
        df = _get_df(request.table_name)
        column_names = df.columns.tolist()

        result = await ask_question(request.question, request.table_name, column_names, engine)
        return result

    except Exception as e:
        logger.error(f"Ask question error: {e}")
        return {
            "success": False,
            "error": str(e),
            "question": request.question
        }
