import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import logging
from app.database import engine
from app.utils.file_processing import ensure_upload_dir, read_dataset, detect_schema, clean_dataframe
from app.services.profiling import profile_dataset
from app.core.config import settings
from app.core.globals import _datasets
import pandas as pd

router = APIRouter(tags=["Upload"])
logger = logging.getLogger(__name__)


# Upload router
@router.post('/upload')
async def upload_dataset(file: UploadFile = File(...), name: str = Form(...)):
    ensure_upload_dir(settings.upload_dir)
    
    # 1. Validate File Extension
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
    filename_lower = file.filename.lower()
    ext = os.path.splitext(filename_lower)[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload CSV or Excel (.csv, .xlsx, .xls)."
        )

    # 2. Validate File Size (10MB limit)
    MAX_UPLOAD_MB = 10
    MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
    
    # Check size by seeking to end
    # Note: Starlette 0.27 UploadFile.seek does not support whence argument
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_MB}MB."
        )

    # 3. Save File
    uid = uuid.uuid4().hex
    filename = f"{uid}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    
    with open(path, 'wb') as f:
        # We read chunks to avoid memory issues, though 10MB is small enough to read at once often
        while content := await file.read(1024 * 1024):  # 1MB chunks
            f.write(content)

    # 4. Load Data (Handle CSV vs Excel)
    try:
        if ext == ".csv":
            df = read_dataset(path)
        else:
            # For Excel, we default to the first sheet
            df = pd.read_excel(path) 
            
        logger.info("Loaded DataFrame shape: %s", df.shape)
        logger.debug("Loaded DataFrame columns: %s", df.columns.tolist())
        
        # Check if all columns are 'Unnamed' (indicates missing header)
        if all(str(col).startswith('Unnamed') for col in df.columns):
            logger.info("All columns are unnamed. Reloading with header=None.")
            if ext == ".csv":
                 df = pd.read_csv(path, header=None)
            else:
                 df = pd.read_excel(path, header=None)
            # Assign string columns
            df.columns = [f"Column_{i+1}" for i in range(df.shape[1])]

        df_clean, info = clean_dataframe(df)
        
        if df_clean.empty or len(df_clean.columns) == 0:
             raise Exception("Dataset contains no valid data or columns after cleaning.")
        schema = detect_schema(df_clean)

        # store into DB as a new table
        table_name = f"dataset_{uid}"
        df_clean.to_sql(table_name, con=engine, index=False, if_exists='replace')
        
        # Store dataframe in memory for analytics
        _datasets[table_name] = df_clean

        # Generate profile
        profile = profile_dataset(df_clean)

        # Determine sheet name used (for metadata)
        sheet_used = "Sheet1" 
        if ext in ['.xlsx', '.xls']:
            try:
                xl = pd.ExcelFile(path)
                if xl.sheet_names:
                    sheet_used = xl.sheet_names[0]
            except Exception:
                 pass

        # save metadata
        meta = {
            'name': name,
            'path': path,
            'schema': schema,
            'rows': info['rows'],
            'table_name': table_name,
            'columns': info['columns'],
            'profile': profile,
            'sheet_used': sheet_used if ext in ['.xlsx', '.xls'] else None 
        }
    except Exception as e:
        # If parsing or processing fails, cleanup and error
        # DEBUG: Do not remove file to inspect it
        # if os.path.exists(path):
        #     os.remove(path)
        
        # Log the full error for debugging (print to console which Uvicorn catches)
        logger.exception("Error processing file %s: %s", filename, str(e))
        
        # Log first 50 bytes to see header
        try:
            with open(path, 'rb') as f:
                header = f.read(50)
                logger.debug("File Header (hex): %s", header.hex())
                logger.debug("File Header (repr): %r", header)
        except Exception:
            pass

        raise HTTPException(
            status_code=400,
            detail="Failed to process file: invalid format or corrupted data."
        )

    return JSONResponse(content={'status': 'ok', 'metadata': meta})
