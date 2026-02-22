import sqlite3
import pandas as pd
import requests

conn = sqlite3.connect('insightiq.db')
query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';"
tables = pd.read_sql(query, conn)
if not tables.empty:
    latest_table = tables['name'].iloc[-1]
    res = requests.post('http://127.0.0.1:8000/api/forecast', json={'table_name': latest_table, 'periods': 3})
    data = res.json()
    print("STATUS CODE:", res.status_code)
    print("SUCCESS:", data.get('success'))
    print("STATUS:", data.get('status'))
    print("MESSAGE:", data.get('message'))
    print("CURRENCY:", data.get('currency'))
