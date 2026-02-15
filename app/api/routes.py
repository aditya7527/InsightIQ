import os
import time
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import text
from app.db.session import engine
from app.utils.file_processing import ensure_upload_dir, read_dataset, detect_schema, clean_dataframe
from app.core.config import settings
from app.schemas import DatasetCreate, InsightOut
from app.services.analytics import generate_sql, run_sql
from app.services.gpt_service import generate_insights_text
import pandas as pd
import os

router = APIRouter()

# Store current datasets in memory for analytics
_datasets = {}


@router.post('/upload')
async def upload_dataset(file: UploadFile = File(...), name: str = Form(...)):
    ensure_upload_dir(settings.upload_dir)
    ext = os.path.splitext(file.filename)[1]
    uid = uuid.uuid4().hex
    filename = f"{uid}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, 'wb') as f:
        content = await file.read()
        f.write(content)

    df = read_dataset(path)
    df_clean, info = clean_dataframe(df)
    schema = detect_schema(df_clean)

    # store into DB as a new table
    table_name = f"dataset_{uid}"
    df_clean.to_sql(table_name, con=engine, index=False, if_exists='replace')
    
    # Store dataframe in memory for analytics
    _datasets[table_name] = df_clean

    # save metadata (simple file-based for this scaffold)
    meta = {
        'name': name,
        'path': path,
        'schema': schema,
        'rows': info['rows'],
        'table_name': table_name,
        'columns': info['columns'],
    }
    return JSONResponse(content={'status': 'ok', 'metadata': meta})


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
        
        # Calculate column statistics
        column_stats = {}
        for col in df.columns:
            non_null = df[col].notna().sum()
            total = len(df)
            missing_percent = ((total - non_null) / total * 100) if total > 0 else 0
            
            column_stats[col] = {
                'non_null_count': int(non_null),
                'missing_percent': round(missing_percent, 2),
                'dtype': str(df[col].dtype),
            }
        
        # Calculate numeric summary
        numeric_summary = []
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            numeric_summary.append({
                'name': col,
                'min': float(df[col].min()) if not pd.isna(df[col].min()) else None,
                'max': float(df[col].max()) if not pd.isna(df[col].max()) else None,
                'mean': float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                'median': float(df[col].median()) if not pd.isna(df[col].median()) else None,
                'std': float(df[col].std()) if not pd.isna(df[col].std()) else None,
                'count': int(df[col].count()),
            })
        
        # Get categorical summary
        categorical_summary = []
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols[:5]:  # Limit to first 5 categorical columns
            value_counts = df[col].value_counts().head(5).to_dict()
            categorical_summary.append({
                'name': col,
                'unique_values': int(df[col].nunique()),
                'top_values': value_counts,
            })
        
        return {
            'column_stats': column_stats,
            'numeric_summary': numeric_summary,
            'categorical_summary': categorical_summary,
            'total_rows': len(df),
            'total_columns': len(df.columns),
        }
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


@router.get('/export/csv/{table_name}')
def export_csv(table_name: str):
    sql = f"SELECT * FROM {table_name} LIMIT 100000"
    rows = run_sql(engine, sql)
    if not rows:
        raise HTTPException(status_code=404, detail='Table empty')
    df = pd.DataFrame(rows)
    path = os.path.join(settings.upload_dir, f"export_{table_name}.csv")
    df.to_csv(path, index=False)
    return FileResponse(path, media_type='text/csv', filename=os.path.basename(path))



@router.get('/export/json/{table_name}')
def export_json(table_name: str):
    sql = f"SELECT * FROM {table_name} LIMIT 100000"
    rows = run_sql(engine, sql)
    return {'rows': rows}
