import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-flash-latest")

print("Testing gemini-flash-latest...")
try:
    start = time.time()
    response = model.generate_content("Hello")
    print(f"Success! {time.time()-start:.2f}s")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
