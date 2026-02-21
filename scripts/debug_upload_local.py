
import asyncio
import os
import io
import sys
sys.path.append(os.getcwd())
import pandas as pd
from fastapi import UploadFile
from app.routers.upload import upload_dataset

# Mock settings just in case
from app.core.config import settings
# Ensure upload dir
if not os.path.exists(settings.upload_dir):
    os.makedirs(settings.upload_dir)

async def debug_upload():
    print("Starting debug...")
    
    # Create dummy excel content
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    
    try:
        # Known good instantiation (kwargs)
        file_obj = UploadFile(file=buffer, filename="debug_test.xlsx")
        print("Instantiation SUCCESS")
    except TypeError as e:
        print(f"Instantiation FAILED: {e}")
        return

    try:
        response = await upload_dataset(file=file_obj, name="Debug Upload")
        print("Success:", response)
        # print("Body:", response.body) 
    except Exception as e:
        print("CRASHED:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_upload())
