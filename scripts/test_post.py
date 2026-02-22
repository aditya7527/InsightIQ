import sqlite3
import requests
import json
import time

try:
    conn = sqlite3.connect('insightiq.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';")
    tables = cursor.fetchall()
    
    for t in tables:
        table_name = t[0]
        print(f"Testing {table_name}:")
        start = time.time()
        res = requests.post('http://127.0.0.1:8000/api/root-cause', json={"table_name": table_name, "metric_column": "Revenue"})
        end = time.time()
        print(f"Status: {res.status_code}, Time: {end-start:.2f}s")
        print("Response:", res.json())
        print("-" * 40)
except Exception as e:
    import traceback
    traceback.print_exc()
