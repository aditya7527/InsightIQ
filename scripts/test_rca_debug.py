import sqlite3
import pandas as pd
import json
import logging
import traceback
from app.services.root_cause_analysis import analyze_root_causes

logging.basicConfig(level=logging.DEBUG)

def test_rca():
    conn = sqlite3.connect("insightiq.db")
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)
    for t in tables["name"]:
        if t.startswith("dataset_"):
            print("Testing table:", t)
            df = pd.read_sql(f"SELECT * FROM \"{t}\"", conn)
            
            qty_col = next((c for c in df.columns if "quantity" in c.lower() or "qty" in c.lower()), None)
            price_col = next((c for c in df.columns if "price" in c.lower() or "unitprice" in c.lower()), None)
            
            if qty_col and price_col:
                df["Revenue"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0) * pd.to_numeric(df[price_col], errors="coerce").fillna(0)
            
            metric = "Revenue" if "Revenue" in df.columns else (df.select_dtypes(include="number").columns[0] if len(df.select_dtypes(include="number").columns) > 0 else None)
            if not metric: 
                 continue
                 
            try:
                res = analyze_root_causes(df, metric)
                print("Result ok")
            except Exception as e:
                print("ERROR HAPPENED!")
                traceback.print_exc()
                import sys
                sys.exit(1)

test_rca()
