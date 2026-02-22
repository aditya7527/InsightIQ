from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import pandas as pd
import os
import logging
from app.core.config import settings
from app.services.analytics import run_sql
from app.pdf.generator import generate_executive_report
from app.services.confidence_score import calculate_confidence_score
from app.services.industry_detection import detect_industry
from app.database import engine
from app.utils.sql_safety import validate_dataset_table_name, ensure_table_exists

router = APIRouter(tags=["Export"])
logger = logging.getLogger(__name__)

class ReportRequest(BaseModel):
    table_name: str
    include_forecast: bool = False

@router.post("/report/export-pdf")
def export_pdf_report(request: ReportRequest):

    """
    Generate and download executive PDF report
    """
    table_name = request.table_name
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        ensure_table_exists(engine, safe_table_name)
        # Get analytics data
        rows = run_sql(engine, f'SELECT * FROM "{safe_table_name}"')
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
            dataset_name=safe_table_name,
            analytics_data=analytics_data,
            confidence_score=confidence_score,
            industry=industry
        )
        
        filename = f"Report_{safe_table_name}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Reset buffer pointer
        pdf_buffer.seek(0)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        raise HTTPException(status_code=400, detail="Failed to generate PDF report due to an internal error.")


@router.get('/export/csv/{table_name}')
def export_csv(table_name: str):
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        ensure_table_exists(engine, safe_table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sql = f'SELECT * FROM "{safe_table_name}" LIMIT 100000'
    rows = run_sql(engine, sql)
    if not rows:
        raise HTTPException(status_code=404, detail='Table empty')
    df = pd.DataFrame(rows)
    path = os.path.join(settings.upload_dir, f"export_{safe_table_name}.csv")
    df.to_csv(path, index=False)
    return FileResponse(path, media_type='text/csv', filename=os.path.basename(path))


@router.get('/export/json/{table_name}')
def export_json(table_name: str):
    try:
        safe_table_name = validate_dataset_table_name(table_name)
        ensure_table_exists(engine, safe_table_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sql = f'SELECT * FROM "{safe_table_name}" LIMIT 100000'
    rows = run_sql(engine, sql)
    return {'rows': rows}
