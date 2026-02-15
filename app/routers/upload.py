import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.database import engine
from app.utils.file_processing import ensure_upload_dir, read_dataset, detect_schema, clean_dataframe
from app.services.profiling import profile_dataset
from app.core.config import settings
from app.core.globals import _datasets
import pandas as pd

router = APIRouter(tags=["Upload"])


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

    # Generate profile
    profile = profile_dataset(df_clean)

    # save metadata
    meta = {
        'name': name,
        'path': path,
        'schema': schema,
        'rows': info['rows'],
        'table_name': table_name,
        'columns': info['columns'],
        'profile': profile
    }
    return JSONResponse(content={'status': 'ok', 'metadata': meta})
