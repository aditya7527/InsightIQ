import time
from fastapi import APIRouter, HTTPException, Form
from app.database import engine
from app.services.analytics import generate_sql, run_sql
from app.core.globals import _datasets
from app.services.profiling import profile_dataset
import pandas as pd
from app.ai.gpt_service import generate_insights_text

router = APIRouter(tags=["Analytics"])


@router.get('/analytics/{table_name}')
def get_analytics(table_name: str):
    """Get comprehensive analytics for a dataset"""
    try:
        # Try to get from memory first
        if table_name in _datasets:
            df = _datasets[table_name]
        else:
            # Fall back to loading from database
            sql = f"SELECT * FROM {table_name}"
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/analytics/template/{template}/{table_name}')
def analytics(template: str, table_name: str):
    sql = generate_sql(template, table_name)
    if not sql:
        raise HTTPException(status_code=400, detail='Unknown template')
    rows = run_sql(engine, sql)
    return {'rows': rows}


@router.post('/insights')
def insights(table_name: str = Form(...), template: str = Form(...)):
    start = time.time()
    sql = generate_sql(template, table_name)
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

    analysis_payload = {'template': template, 'table': table_name, 'rows_sample': rows[:20]}
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
