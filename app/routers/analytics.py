import time
from fastapi import APIRouter, HTTPException, Form
import logging
from app.database import engine
from app.services.analytics import generate_sql, run_sql
from app.core.globals import _datasets
from app.services.profiling import profile_dataset
from app.utils.sql_safety import validate_dataset_table_name, ensure_table_exists
import pandas as pd
from app.ai.gpt_service import generate_insights_text

router = APIRouter(tags=["Analytics"])
logger = logging.getLogger(__name__)


@router.get('/analytics/{table_name}')
def get_analytics(table_name: str):
    """Get comprehensive analytics for a dataset"""
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        # Try to get from memory first
        if safe_table_name in _datasets:
            df = _datasets[safe_table_name]
        else:
            # Fall back to loading from database
            ensure_table_exists(engine, safe_table_name)
            sql = f'SELECT * FROM "{safe_table_name}"'
            rows = run_sql(engine, sql)
            df = pd.DataFrame(rows)
        
        if df.empty:
             return {
                'column_stats': {},
                'numeric_summary': [],
                'categorical_summary': [],
                'total_rows': 0,
                'total_columns': 0,
            }

        # Generate profile using the service
        profile = profile_dataset(df)
        
        return profile
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Analytics failed for table=%s", table_name)
        raise HTTPException(status_code=400, detail="Analytics failed.")


@router.get('/analytics/template/{template}/{table_name}')
def analytics(template: str, table_name: str):
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        ensure_table_exists(engine, safe_table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sql = generate_sql(template, safe_table_name)
    if not sql:
        raise HTTPException(status_code=400, detail='Unknown template')
    rows = run_sql(engine, sql)
    return {'rows': rows}


@router.post('/insights')
def insights(table_name: str = Form(...), template: str = Form(...)):
    start = time.time()
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        ensure_table_exists(engine, safe_table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sql = generate_sql(template, safe_table_name)
    if not sql:
        raise HTTPException(status_code=400, detail='Unknown template')
    rows = run_sql(engine, sql)

    # Simple numeric validation / confidence
    df = pd.DataFrame(rows)
    completeness = 1.0
    if df.empty:
        completeness = 0.0
    else:
        completeness = df.notnull().sum().sum() / (df.size if df.size>0 else 1)

    analysis_payload = {'template': template, 'table': safe_table_name, 'rows_sample': rows[:20]}
    ai_out = generate_insights_text(analysis_payload)
    latency = int((time.time() - start) * 1000)

    out = {
        'summary': ai_out.get('summary', ''),
        'kpis': ai_out.get('kpis', []),
        'risks': ai_out.get('risks', []),
        'recommendations': ai_out.get('recommendations', []),
        'confidence': float(completeness),
        'latency_ms': latency,
    }
    return out
