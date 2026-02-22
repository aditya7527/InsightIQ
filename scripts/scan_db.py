import sqlite3
import pandas as pd

conn = sqlite3.connect('insightiq.db')
datasets = pd.read_sql('SELECT * FROM datasets', conn)
print("Available Datasets:")
print(datasets[['name', 'table_name']])

for _, row in datasets.iterrows():
    name = row['name']
    t_name = row['table_name']
    print(f"\nScanning table: {t_name} (Name: {name})")
    try:
        df = pd.read_sql(f'SELECT * FROM "{t_name}" LIMIT 5', conn)
        print("Columns:", df.columns.tolist())
    except Exception as e:
        print(f"Error reading table {t_name}: {e}")

conn.close()
