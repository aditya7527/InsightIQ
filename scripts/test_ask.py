import requests, sqlite3, pandas as pd
conn = sqlite3.connect('insightiq.db')
name = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dataset_%';", conn).iloc[-1]['name']
r = requests.post('http://127.0.0.1:8000/api/ask', json={'table_name': name, 'question': 'what is the total revenue?'})
import pprint
pprint.pprint(r.json())
