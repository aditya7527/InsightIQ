"""
Advanced AI Features Routes
Ask Your Data, Root Cause Analysis, Confidence Scoring, Forecasting
"""
from fastapi import APIRouter, Form, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
import pandas as pd
from sqlalchemy import create_engine, text
import logging
from typing import Optional

from app.core.config import settings
from app.services.confidence_score import calculate_confidence_score
from app.services.industry_detection import detect_industry
from app.services.forecasting import (
    auto_detect_date_column, 
    auto_detect_revenue_column,
    forecast_linear
)
from app.services.root_cause_analysis import analyze_root_causes, detect_anomalies
from app.services.conversational_ai import ask_question
from app.services.pdf_report import generate_executive_report
from app.api.routes import _datasets, run_sql, engine

router = APIRouter(tags=["AI Features"])
logger = logging.getLogger(__name__)


# ========== CONFIDENCE SCORE ENDPOINT ==========
@router.get("/confidence/{table_name}")
def get_confidence_score(table_name: str):
    """
    Get data quality and confidence score for a dataset
    
    Response:
    {
        "confidence_score": 87,
        "data_quality": "Good",
        "completeness": 95,
        "row_count_score": 80,
        "outlier_ratio": 0.02
    }
    """
    try:
        # Get dataframe from cache or database
        if table_name in _datasets:
            df = _datasets[table_name]
        else:
            # Load from database
            rows = run_sql(engine, f"SELECT * FROM {table_name} LIMIT 10000")
            df = pd.DataFrame(rows)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Get column stats (from analytics)
        sql = f"SELECT * FROM {table_name}"
        all_rows = run_sql(engine, sql)
        full_df = pd.DataFrame(all_rows)
        
        column_stats = {}
        for col in full_df.columns:
            non_null = full_df[col].notna().sum()
            total = len(full_df)
            missing_percent = ((total - non_null) / total * 100) if total > 0 else 0
            column_stats[col] = {'missing_percent': missing_percent}
        
        # Calculate confidence
        confidence, quality = calculate_confidence_score(df, column_stats)
        
        return {
            "confidence_score": confidence,
            "data_quality": quality,
            "table_name": table_name,
            "rows_analyzed": len(df),
            "columns": len(df.columns)
        }
    
    except Exception as e:
        logger.error(f"Confidence score error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== INDUSTRY DETECTION ENDPOINT ==========
@router.get("/industry/{table_name}")
def detect_industry_endpoint(table_name: str):
    """
    Auto-detect business industry and get KPI recommendations
    
    Response:
    {
        "industry": "retail",
        "confidence": 85,
        "recommended_kpis": [...],
        "recommended_metrics": [...]
    }
    """
    try:
        # Get dataframe
        if table_name in _datasets:
            df = _datasets[table_name]
        else:
            rows = run_sql(engine, f"SELECT * FROM {table_name} LIMIT 100")
            df = pd.DataFrame(rows)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Detect industry
        industry, recommendations = detect_industry(df, df.columns.tolist())
        
        return recommendations
    
    except Exception as e:
        logger.error(f"Industry detection error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== ROOT CAUSE ANALYSIS ENDPOINT ==========
@router.post("/root-cause")
def analyze_root_cause(
    table_name: str = Form(...),
    metric_column: Optional[str] = Form(None),
    group_by: Optional[str] = Form(None)
):
    """
    Analyze root causes of metric changes
    
    Request:
    {
        "table_name": "dataset_xyz",
        "metric_column": "Revenue",
        "group_by": "Region, Category"  # optional, comma-separated
    }
    
    Response:
    {
        "metric": "Revenue",
        "current_value": 125000,
        "kpi_change_percent": -12.4,
        "top_drivers": [...],
        "recommendations": [...]
    }
    """
    try:
        # Get dataframe
        if table_name in _datasets:
            df = _datasets[table_name]
        else:
            rows = run_sql(engine, f"SELECT * FROM {table_name}")
            df = pd.DataFrame(rows)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Auto-detect metric if not provided
        if not metric_column:
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                metric_column = numeric_cols[-1]  # Last numeric column
            else:
                raise HTTPException(status_code=400, detail="No numeric column found")
        
        # Parse group by columns
        group_cols = None
        if group_by:
            group_cols = [col.strip() for col in group_by.split(',')]
            group_cols = [col for col in group_cols if col in df.columns]
        
        # Analyze
        analysis = analyze_root_causes(df, metric_column, group_cols or None)
        anomalies = detect_anomalies(df, metric_column)
        
        analysis['anomalies'] = anomalies[:5]
        
        return analysis
    
    except Exception as e:
        logger.error(f"Root cause analysis error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== FORECASTING ENDPOINT ==========
@router.post("/forecast")
def forecast_endpoint(
    table_name: str = Form(...),
    periods: int = Form(6),
    method: str = Form("linear")
):
    """
    Forecast future values
    
    Request:
    {
        "table_name": "dataset_xyz",
        "periods": 6,
        "method": "linear"  # or "exponential"
    }
    
    Response:
    {
        "forecast": [
            {"date": "2026-03-15", "predicted": 124000, "period": 1},
            ...
        ],
        "date_column": "Date",
        "value_column": "Revenue"
    }
    """
    try:
        # Get dataframe
        if table_name in _datasets:
            df = _datasets[table_name]
        else:
            rows = run_sql(engine, f"SELECT * FROM {table_name}")
            df = pd.DataFrame(rows)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Auto-detect date and revenue columns
        date_col = auto_detect_date_column(df)
        value_col = auto_detect_revenue_column(df)
        
        if not date_col or not value_col:
            raise HTTPException(
                status_code=400,
                detail=f"Could not auto-detect date/revenue columns. Need at least 2 rows."
            )
        
        # Generate forecast
        forecast = forecast_linear(df, date_col, value_col, periods)
        
        return {
            "success": True,
            "forecast": forecast,
            "date_column": date_col,
            "value_column": value_col,
            "periods": periods,
            "method": method
        }
    
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== ASK YOUR DATA ENDPOINT ==========
@router.post("/ask")
async def ask_data_endpoint(
    table_name: str = Form(...),
    question: str = Form(...)
):
    """
    Ask natural language questions about your data
    
    Request:
    {
        "table_name": "dataset_xyz",
        "question": "Why did revenue drop in Q3?"
    }
    
    Response:
    {
        "success": true,
        "question": "...",
        "sql": "SELECT ...",
        "results": [...],
        "explanation": "..."
    }
    """
    try:
        # Get dataframe to extract column names
        if table_name in _datasets:
            df = _datasets[table_name]
            column_names = df.columns.tolist()
        else:
            rows = run_sql(engine, f"SELECT * FROM {table_name} LIMIT 1")
            df = pd.DataFrame(rows)
            column_names = df.columns.tolist() if not df.empty else []
        
        if not column_names:
            raise HTTPException(status_code=404, detail="Dataset not found or empty")
        
        # Process question
        result = await ask_question(question, table_name, column_names, engine)
        
        return result
    
    except Exception as e:
        logger.error(f"Ask question error: {e}")
        return {
            "success": False,
            "error": str(e),
            "question": question
        }


# ========== EXECUTIVE REPORT ENDPOINT ==========
@router.post("/report/export-pdf")
def export_pdf_report(
    table_name: str = Form(...),
    include_forecast: bool = Form(False)
):
    """
    Generate and download executive PDF report
    
    Returns:
        PDF file for download
    """
    try:
        # Get analytics data
        rows = run_sql(engine, f"SELECT * FROM {table_name}")
        df = pd.DataFrame(rows)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Calculate metrics
        confidence_score, quality = calculate_confidence_score(df, {})
        industry, industry_info = detect_industry(df, df.columns.tolist())
        
        # Build analytics data
        analytics_data = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'numeric_summary': [],
            'categorical_summary': []
        }
        
        # Add numeric columns
        for col in df.select_dtypes(include=['number']).columns[:5]:
            analytics_data['numeric_summary'].append({
                'name': col,
                'mean': float(df[col].mean()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'std': float(df[col].std())
            })
        
        # Generate report
        pdf_buffer = generate_executive_report(
            dataset_name=table_name,
            analytics_data=analytics_data,
            confidence_score=confidence_score,
            industry=industry
        )
        
        return FileResponse(
            pdf_buffer,
            media_type="application/pdf",
            filename=f"Report_{table_name}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
    
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
