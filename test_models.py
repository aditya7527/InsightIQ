import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-pro"]

print("Testing Gemini Models for availability...")

for m_name in models:
    print(f"\n--- Testing {m_name} ---")
    try:
        model = genai.GenerativeModel(m_name)
        start = time.time()
        response = model.generate_content("Hi, reply with 'OK' if you see this.")
        print(f"SUCCESS ({time.time()-start:.2f}s): {response.text}")
    except Exception as e:
        print(f"FAILED: {e}")
