import requests, sqlite3, pandas as pd
conn = sqlite3.connect('insightiq.db')
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';", conn)
print(requests.get(f"http://127.0.0.1:8000/api/summary/{tables['name'].iloc[-1]}").json())
