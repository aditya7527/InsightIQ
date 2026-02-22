import requests, sqlite3, pandas as pd

conn = sqlite3.connect('insightiq.db')
query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';"
tables = pd.read_sql(query, conn)
if not tables.empty:
    latest_table = tables['name'].iloc[-1]
    res = requests.get(f'http://127.0.0.1:8000/api/summary/{latest_table}')
    print("STATUS:", res.status_code)
    try:
        data = res.json()
        print('Summary:', str(data.get('summary', ''))[:100])
        print('Next steps:', data.get('next_steps', []))
    except Exception as e:
        print('Error:', e)
