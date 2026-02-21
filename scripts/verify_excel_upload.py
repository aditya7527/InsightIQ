
import requests
import pandas as pd
import io
import os

# Create a dummy Excel file
df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    df.to_excel(writer, index=False)
excel_buffer.seek(0)

url = 'http://localhost:8000/api/upload'
files = {'file': ('test.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
data = {'name': 'Test Excel Upload'}

try:
    response = requests.post(url, files=files, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS: Excel upload successful!")
    else:
        print("FAILURE: Upload upload failed.")
        
except Exception as e:
    print(f"ERROR: {e}")
