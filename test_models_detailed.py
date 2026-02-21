import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key missing")
    exit(1)

genai.configure(api_key=api_key)

models_to_test = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash", 
    "gemini-1.5-pro",
    "gemini-pro"
]

print("Testing Model Availability:\n")

for m_name in models_to_test:
    print(f"--- Trying {m_name} ---")
    try:
        model = genai.GenerativeModel(m_name)
        start = time.time()
        response = model.generate_content("Hello")
        elapsed = time.time() - start
        print(f"[SUCCESS] {m_name} responded in {elapsed:.2f}s")
        print(f"Response: {response.text[:50]}...")
    except Exception as e:
        print(f"[FAILED] {m_name}: {e}")
    print("-" * 30)
