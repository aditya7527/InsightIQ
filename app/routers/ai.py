from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import pandas as pd
import logging

from app.core.globals import _datasets
from app.services.industry_detection import detect_industry, get_industry_context
from app.services.root_cause_analysis import analyze_root_causes
from app.ai.conversational import ask_question
from app.ai.gpt_service import query_gpt
from app.services.analytics import run_sql
from app.database import engine
from app.utils.sql_safety import validate_dataset_table_name, ensure_table_exists

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
    safe_table_name = validate_dataset_table_name(table_name)
    if safe_table_name in _datasets:
        return _datasets[safe_table_name]
    ensure_table_exists(engine, safe_table_name)
    rows = run_sql(engine, f'SELECT * FROM "{safe_table_name}"')
    df = pd.DataFrame(rows)
    if df.empty:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return df


# Revenue computation delegated to revenue_engine to avoid duplicate logic
# DO NOT COMPUTE REVENUE OUTSIDE revenue_engine.py
from app.services.revenue_engine import (
    _try_compute_revenue,
    compute_monthly_revenue,
    detect_date_column,
    detect_revenue_column,
    get_monthly_series_from_result
)
from app.services.forecasting_service import generate_forecast
from app.services.root_cause_analysis import analyze_root_causes
from app.services.trust_engine import compute_trust_index



# ========== CONFIDENCE SCORE (Data-Driven Integrity) ==========
@router.get("/confidence/{table_name}")
def get_confidence_score(table_name: str):
    try:
        df = _get_df(table_name)
        df = _try_compute_revenue(df)
        
        date_col = detect_date_column(df)
        rev_col  = detect_revenue_column(df)
        
        trust_res = {
            "trust_score": 0.0,
            "trust_label": "Insufficient Data"
        }
        
        integrity_score, integrity_quality, penalty_reasons = 0, "Unknown", []
        
        if date_col and rev_col:
            try:
                # 1. Base revenue
                rev_result = compute_monthly_revenue(df, date_col, rev_col)
                monthly_series = get_monthly_series_from_result(rev_result)
                volatility_cv = rev_result.get("volatility", {}).get("cv", 1.0)
                
                # 2. Forecast Output
                import logging
                logger.info("Computing trust index forecast data...")
                forecast_data = generate_forecast(df, rev_col, date_col, periods=3, rev_result=rev_result)
                model_metrics = forecast_data.get("metrics", {})
                
                # 3. Significance Result
                # analyze_root_causes requires df, metric_col, group_cols
                logger.info("Computing trust index root cause data...")
                rca_data = analyze_root_causes(df, rev_col, None, rev_result=rev_result)
                significance_result = {
                    "p_value": rca_data.get("p_value", 1.0),
                    "is_significant": rca_data.get("is_significant", False)
                }
                
                # Compute composite trust
                trust_res = compute_trust_index(
                    df=df,
                    monthly_series=monthly_series,
                    model_metrics=model_metrics,
                    significance_result=significance_result,
                    volatility_cv=volatility_cv
                )
                
            except Exception as e:
                import traceback
                logger.warning("Trust Engine error: %s\n%s", e, traceback.format_exc())
                pass

        return {
            "trust_score": trust_res["trust_score"],
            "trust_label": trust_res["trust_label"],
            "components": trust_res.get("components", []),
            "limiting_factor": trust_res.get("limiting_factor", ""),
            "explanation": trust_res.get("explanation", ""),
            "confidence_score": int(trust_res["trust_score"] * 100),
            "confidence_score_quality": trust_res["trust_label"],
            "table_name": table_name,
            "rows_analyzed": len(df),
            "columns": len(df.columns),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Confidence score error: %s", e)
        raise HTTPException(status_code=500, detail="Could not compute integrity score.")


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
        df = _try_compute_revenue(df)

        industry, _ = detect_industry(df, df.columns.tolist())

        try:
            profile = profile_dataset(df)
        except Exception as prof_err:
            logger.warning("profile_dataset failed in summary: %s", prof_err)
            profile = {'computed_metrics': []}

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
            from app.utils.file_processing import detect_currency, format_currency
            rev_val = revenue_metric['value']
            currency = detect_currency(df)
            rev_formatted = format_currency(rev_val, currency)
            summary_lines.append(f"Total Revenue: {rev_formatted}.")
        if aov_metric:
            from app.utils.file_processing import detect_currency, format_currency
            currency = detect_currency(df)
            summary_lines.append(f"Average Order Value: {format_currency(aov_metric['value'], currency)}.")
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
                if "error" not in gpt_data:
                    return gpt_data
        except Exception:
            pass

        return {
            "summary": " ".join(summary_lines),
            "next_steps": next_steps
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("Summary endpoint error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail="Executive summary generation failed. Please try again.")


# ========== ROOT CAUSE ANALYSIS ==========
@router.post("/root-cause")
def analyze_root_cause(request: RootCauseRequest):
    """Analyze root causes of revenue changes — normalized and thresholded."""
    try:
        df = _get_df(request.table_name)
        df = _try_compute_revenue(df)

        # Detect metric column — prefer Revenue, then use request, then auto-detect
        if 'Revenue' in df.columns:
            metric_column = 'Revenue'
        elif request.metric_column and request.metric_column in df.columns:
            metric_column = request.metric_column
        else:
            metric_column = detect_revenue_column(df)

        if not metric_column:
            return {
                'current_period': None, 'previous_period': None,
                'current_value': 0, 'previous_value': None,
                'change_percent': None, 'top_drivers': [],
                'insight_summary': 'No numeric revenue column found.',
                'recommendations': ['Upload a dataset with a Sales, Revenue or Amount column.']
            }

        group_cols = request.group_by
        if group_cols:
            group_cols = [c for c in group_cols if c in df.columns]

        analysis = analyze_root_causes(df, metric_column, group_cols)

        # Add anomalies
        try:
            anomalies = detect_anomalies(df, metric_column)
            analysis['anomalies'] = anomalies[:5]
        except Exception:
            analysis['anomalies'] = []

        return analysis

    except Exception as e:
        import traceback
        logger.error("Root cause error: %s\n%s", e, traceback.format_exc())
        return {
            'current_period': None, 'previous_period': None,
            'current_value': 0, 'previous_value': None,
            'change_percent': None, 'top_drivers': [],
            'insight_summary': 'Root cause analysis encountered a data processing error. Ensure your dataset has date and revenue columns.',
            'recommendations': ['Check that your dataset has a valid date column and numeric revenue column.']
        }


# ========== FORECASTING ==========
@router.post("/forecast")
def forecast_endpoint(request: ForecastRequest):
    """
    Generate production-grade forecast (SARIMAX/HW) with reliability scores.
    """
    try:
        from app.services.forecasting_service import generate_forecast
        
        df = _get_df(request.table_name)
        df = _try_compute_revenue(df)
        
        # Identify columns
        revenue_col = 'Revenue' if 'Revenue' in df.columns else auto_detect_revenue_column(df)
        date_col = auto_detect_date_column(df)
        
        if not revenue_col or not date_col:
             return {
                 "success": False,
                 "message": "Could not identify Date or Revenue columns."
             }

        # Generate Forecast
        result = generate_forecast(df, revenue_col, date_col, periods=request.periods)
        
        return result

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Forecast endpoint error: {e}\n{error_trace}")
        return {
            'success': False,
            'forecast': [],
            'historical': [],
            'message': "Forecast failed due to internal error."
        }


# ========== NARRATIVE / SUMMARY ==========
@router.post("/summary/deterministic")
def summary_deterministic(request: RootCauseRequest):
    """
    Generate deterministic narratives combining forecast and root cause data.
    This replaces/augments the LLM-based summary.
    """
    try:
        from app.services.forecasting_service import generate_forecast
        from app.services.narrative_service import generate_summary as gen_narrative
        
        df = _get_df(request.table_name)
        df = _try_compute_revenue(df)
        
        revenue_col = 'Revenue' if 'Revenue' in df.columns else auto_detect_revenue_column(df)
        date_col = auto_detect_date_column(df)
        
        # 1. Get Forecast Data
        forecast_data = {}
        if revenue_col and date_col:
             forecast_data = generate_forecast(df, revenue_col, date_col, periods=3)
             
        # 2. Get Root Cause Data
        root_cause_data = analyze_root_causes(df, revenue_col, request.group_by)
        
        # 3. Generate Narrative
        narrative = gen_narrative(forecast_data, root_cause_data)
        
        return narrative

    except Exception as e:
        logger.error(f"Narrative error: {e}")
        return {"summary": "Error generating narrative.", "error": "Internal error."}


# ========== ASK YOUR DATA ==========
@router.post("/ask")
async def ask_data_endpoint(request: AskRequest):
    try:
        df = _get_df(request.table_name)
        column_names = df.columns.tolist()

        result = await ask_question(request.question, request.table_name, df)
        return result

    except Exception as e:
        logger.error(f"Ask question error: {e}")
        return {
            "success": False,
            "error": "Failed to process question due to internal data error.",
            "question": request.question
        }


# ========== COHORT ANALYSIS ==========
@router.get("/cohort/{table_name}")
def get_cohort_analysis(table_name: str):
    """Compute structural customer cohort retention matrices."""
    try:
        from app.services.cohort_service import compute_cohort_retention
        df = _get_df(table_name)
        df = _try_compute_revenue(df)
        
        # We need date_col and revenue_col
        date_col = auto_detect_date_column(df)
        revenue_col = 'Revenue' if 'Revenue' in df.columns else auto_detect_revenue_column(df)
        
        if not date_col or not revenue_col:
            return {"status": "insufficient_data", "message": "Could not identify Date or Revenue columns."}
            
        result = compute_cohort_retention(df, date_col, revenue_col)
        return result
        
    except Exception as e:
        logger.error(f"Cohort generation error: {e}")
        return {"status": "error", "message": "Failed to generate cohort retention matrix."}
