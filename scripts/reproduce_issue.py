
import pandas as pd
import requests
import os
import sys

def create_dummy_excel(filename, size_kb):
    print(f"Creating {filename} with target size ~{size_kb}KB...")
    # Create a large dataframe
    df = pd.DataFrame({'col1': range(20000), 'col2': ['A'*50]*20000}) 
    try:
        df.to_excel(filename, index=False)
        print(f"Successfully created {filename}")
    except ImportError as e:
        print(f"FAILED to create Excel file. Missing dependency? {e}")
        return False
    except Exception as e:
        print(f"FAILED to create Excel file: {e}")
        return False
    
    actual_size = os.path.getsize(filename) / 1024
    print(f"File size: {actual_size:.2f} KB")
    return True

def test_upload(filename):
    url = 'http://localhost:8000/api/upload'
    print(f"Uploading {filename} to {url}...")
    
    try:
        with open(filename, 'rb') as f:
            files = {'file': (filename, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            data = {'name': 'Test Upload Repro'}
            response = requests.post(url, files=files, data=data)
            
        print(f"Status Code: {response.status_code}")
        try:
            print("Response JSON:", response.json())
        except:
            print("Response Text:", response.text)
            
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    if not create_dummy_excel("test_repro.xlsx", 960):
        sys.exit(1)
        
    test_upload("test_repro.xlsx")
