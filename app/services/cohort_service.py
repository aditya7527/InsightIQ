"""
Cohort Retention Engine
=======================
Analyzes customer behavior over time using strict month-over-month cohorting.
Provides both customer-count and revenue-weighted retention matrices.
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def detect_customer_column(df: pd.DataFrame) -> Optional[str]:
    """Identify the column most likely to represent a unique customer."""
    for col in df.columns:
        cl = col.lower().replace("_", "").replace("-", "").replace(" ", "")
        if "customerid" in cl or "clientid" in cl or "userid" in cl or "accountid" in cl:
            return col
            
    # Fallback to ID-like columns with decent unique counts but not 100% unique
    # (A 100% unique column is likely a transaction ID)
    potential_cols = []
    for col in df.columns:
        if df[col].dtype in ['object', 'int64', 'string']:
            nunique = df[col].nunique()
            if 0 < nunique < len(df):
                potential_cols.append((col, nunique))
                
    if not potential_cols:
        return None
        
    potential_cols.sort(key=lambda x: x[1])
    # Pick the one with the highest unique count that isn't the primary key
    # Simple heuristic: look for 'id' in name or just return the highest cardinality 
    for col, _ in reversed(potential_cols):
        cl = col.lower()
        if "id" in cl or "customer" in cl or "name" in cl or "email" in cl:
            return col
            
    return None

def compute_cohort_retention(df: pd.DataFrame, date_col: str, revenue_col: str) -> Dict:
    """
    Compute customer cohort retention and revenue-weighted retention.
    Requires date_col, revenue_col. Automatically detects customer_col.
    """
    try:
        df = df.copy()
        customer_col = detect_customer_column(df)
        
        if not customer_col:
            return {"status": "insufficient_data", "message": "No customer identifier found."}

        # Step 1: Normalize Dates
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col, customer_col, revenue_col])
        if len(df) == 0:
            return {"status": "insufficient_data", "message": "No valid data after cleaning."}

        df["order_month"] = df[date_col].dt.to_period("M").dt.to_timestamp()
        
        unique_months = df["order_month"].nunique()
        if unique_months < 3:
            return {"status": "insufficient_data", "message": "Need at least 3 months of data for cohort analysis."}

        # Step 2: Define Acquisition Month
        df["cohort_month"] = df.groupby(customer_col)["order_month"].transform("min")

        # Step 3: Compute Cohort Index
        df["cohort_index"] = (
            (df["order_month"].dt.year - df["cohort_month"].dt.year) * 12 +
            (df["order_month"].dt.month - df["cohort_month"].dt.month)
        )

        # Ensure numeric revenue
        df[revenue_col] = pd.to_numeric(df[revenue_col], errors='coerce').fillna(0)

        # Step 4: Create Retention Matrix (Customer Count)
        cohort_data = df.groupby(["cohort_month", "cohort_index"])[customer_col].nunique().reset_index()
        if cohort_data.empty:
             return {"status": "insufficient_data", "message": "Cohort matrix could not be computed from data."}
             
        cohort_pivot = cohort_data.pivot(index="cohort_month", columns="cohort_index", values=customer_col)

        # Step 5: Convert to Retention %
        if cohort_pivot.empty or cohort_pivot.shape[1] == 0:
             return {"status": "insufficient_data", "message": "Cohort pivot table is empty."}
             
        cohort_size = cohort_pivot.iloc[:, 0]
        # Avoid division by zero
        retention_matrix = cohort_pivot.divide(cohort_size.replace(0, np.nan), axis=0).fillna(0)

        # Step 6: Revenue-Weighted Retention
        rev_data = df.groupby(["cohort_month", "cohort_index"])[revenue_col].sum().reset_index()
        rev_pivot = rev_data.pivot(index="cohort_month", columns="cohort_index", values=revenue_col)
        
        if not rev_pivot.empty and rev_pivot.shape[1] > 0:
            rev_base = rev_pivot.iloc[:, 0].replace(0, np.nan) # prevent div by zero
            rev_matrix = rev_pivot.divide(rev_base, axis=0).fillna(0)
        else:
            rev_matrix = pd.DataFrame()

        # Convert to native types for JSON serialization
        def format_matrix(matrix_df):
            if matrix_df.empty: return []
            result = []
            for idx, row in matrix_df.iterrows():
                try:
                    row_data = {"cohort": str(idx.date())[:7]}
                    for col_idx, val in row.items():
                        if pd.notna(val) and val > 0:
                            row_data[f"month_{col_idx}"] = round(float(val) * 100, 2)
                        else:
                            row_data[f"month_{col_idx}"] = None
                    result.append(row_data)
                except Exception as row_err:
                    logger.warning(f"Error formatting cohort row {idx}: {row_err}")
            return result
        
        ret_matrix_json = format_matrix(retention_matrix)
        rev_matrix_json = format_matrix(rev_matrix)
        sizes = {str(idx.date())[:7]: int(val) for idx, val in cohort_size.items()}
        
        # Summary Metrics
        m1_vals = retention_matrix.get(1, pd.Series(dtype=float)).replace(0, np.nan).dropna()
        m3_vals = retention_matrix.get(3, pd.Series(dtype=float)).replace(0, np.nan).dropna()
        
        avg_m1 = float(m1_vals.mean() * 100) if not m1_vals.empty else 0.0
        avg_m3 = float(m3_vals.mean() * 100) if not m3_vals.empty else 0.0
        
        # Simple lifetime approximation based on retention dropoff
        avg_retention_curve = retention_matrix.mean(axis=0).fillna(0)
        avg_lifetime = float(avg_retention_curve.sum())
        
        confidence = "High Stability" if unique_months >= 12 else ("Moderate Stability" if unique_months >= 6 else "Low Sample Confidence")

        return {
            "status": "ok",
            "retention_matrix": ret_matrix_json,
            "revenue_retention_matrix": rev_matrix_json,
            "cohort_sizes": sizes,
            "months_available": int(retention_matrix.columns.max() or 0),
            "summary_metrics": {
                "avg_month_1_retention": round(avg_m1, 2),
                "avg_month_3_retention": round(avg_m3, 2),
                "avg_lifetime_months": round(avg_lifetime, 2)
            },
            "confidence": confidence,
            "customer_column": customer_col
        }
    except Exception as e:
        import traceback
        logger.error(f"Cohort computation error: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": f"Error computing cohorts: {str(e)}"}
