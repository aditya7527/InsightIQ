import os
import pandas as pd
from typing import Tuple, Dict


def ensure_upload_dir(path: str):
    os.makedirs(path, exist_ok=True)


def read_dataset(filepath: str) -> pd.DataFrame:
    if filepath.lower().endswith(('.xls', '.xlsx')):
        return pd.read_excel(filepath)
    
    # Try different encodings for CSV
    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
    for encoding in encodings:
        try:
            return pd.read_csv(filepath, encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    
    # If all encoding attempts fail, try with errors='ignore'
    return pd.read_csv(filepath, encoding='utf-8', errors='ignore')


def detect_schema(df: pd.DataFrame) -> Dict[str, str]:
    schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
    return schema



def clean_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    info = {}
    
    # 1. Remove unnamed columns
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    # 2. Convert date columns to ISO format
    # Heuristic: look for 'date', 'time', 'year', 'month' in column name or object cols that look like dates
    for col in df.columns:
        if df[col].dtype == 'object':
            # Try to convert to numeric if possible (e.g. "1,000")
            # But first ensure it's string, handling potential mixed types
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            
            # Check if it looks like a date
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                except Exception:
                    pass

    # 3. Fill missing values
    # Numeric: fill with median
    numeric_cols = df.select_dtypes(include=['number']).columns
    for c in numeric_cols:
        if df[c].isnull().any():
            median = df[c].median()
            df[c] = df[c].fillna(median)

    # Categorical: fill with mode or 'Unknown'
    cat_cols = df.select_dtypes(include=['object', 'category']).columns
    for c in cat_cols:
        if df[c].isnull().any():
            try:
                mode = df[c].mode()
                if not mode.empty:
                    df[c] = df[c].fillna(mode[0])
                else:
                    df[c] = df[c].fillna('Unknown')
            except Exception:
                df[c] = df[c].fillna('Unknown')

    # 4. Standardize Date Columns (Ensure ISO string for JSON serialization)
    date_cols = df.select_dtypes(include=['datetime', 'datetimetz']).columns
    for c in date_cols:
        df[c] = df[c].dt.strftime('%Y-%m-%d')
        # Fill missing dates if any (rare after coercion but possible)
        df[c] = df[c].fillna('')

    info['rows'] = len(df)
    info['columns'] = list(df.columns)
    return df, info

