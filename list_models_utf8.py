import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    with open("available_models.txt", "w", encoding="utf-8") as f:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"{m.name}\n")
    print("Success")
except Exception as e:
    with open("available_models.txt", "w", encoding="utf-8") as f:
        f.write(f"Error: {e}")
    print(f"Error: {e}")
