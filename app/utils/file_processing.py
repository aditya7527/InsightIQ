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


import re

def detect_currency(df: pd.DataFrame) -> str:
    """Detect dataset currency using Currency column or Ship Country mapping, defaulting to UNSPECIFIED."""
    # Step 1: Detect Currency column
    for col in df.columns:
        col_lower = str(col).lower()
        if col_lower in ['currency', 'currency_code', 'currencycode']:
            val = df[col].dropna().mode()
            if not val.empty:
                return str(val.iloc[0]).strip().upper()

    # Step 2: Detect via Ship Country
    for col in df.columns:
        col_lower = str(col).lower()
        if col_lower in ['shipcountry', 'ship_country', 'country']:
            val = df[col].dropna().mode()
            if not val.empty:
                tc = str(val.iloc[0]).upper()
                if 'IN' in tc or 'INDIA' in tc: return 'INR'
                if 'US' in tc or 'UNITED STATES' in tc: return 'USD'
                if 'GB' in tc or 'UK' in tc or 'UNITED KINGDOM' in tc: return 'GBP'
                if 'EU' in tc or 'EUROPE' in tc or 'FRANCE' in tc or 'GERMANY' in tc: return 'EUR'

    return "UNSPECIFIED"

def format_currency(value: float, currency_code: str) -> str:
    """Format monetary values according to currency code and magnitude."""
    abs_val = abs(value)
    if abs_val >= 1_000_000:
        formatted_num = f"{value / 1_000_000:g}M"
    elif abs_val >= 1_000:
        formatted_num = f"{value / 1_000:g}K"
    else:
        # Use simple str representation to avoid trailing zeros
        formatted_num = f"{value:g}"

    code = str(currency_code).upper()
    if code == 'INR': return f"₹{formatted_num}"
    if code == 'USD': return f"${formatted_num}"
    if code == 'GBP': return f"£{formatted_num}"
    if code == 'EUR': return f"€{formatted_num}"
    if code == 'UNSPECIFIED' or not code: return f"{formatted_num}"
    return f"{formatted_num} {code}"



def detect_schema(df: pd.DataFrame) -> Dict:
    columns = []
    numeric_cols = list(df.select_dtypes(include=['number']).columns)
    date_cols = list(df.select_dtypes(include=['datetime', 'datetimetz']).columns)
    
    # Handle dates that were stringified
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if dtype_str == 'object':
            # rudimentary check for stringified date
            if 'date' in str(col).lower() and col not in date_cols:
                date_cols.append(col)
                dtype_str = 'datetime'
                
        columns.append({"name": str(col), "dtype": dtype_str})
        
    categorical_cols = [c for c in df.columns if c not in numeric_cols and c not in date_cols]
    
    return {
        "columns": columns,
        "row_count": len(df),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "date_columns": date_cols,
        "currency": detect_currency(df)
    }



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

