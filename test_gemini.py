import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print(f"Key found: {'Yes' if api_key else 'No'}")
if not api_key:
    exit(1)

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    print("Attempting to generate content...")
    response = model.generate_content("Hello, are you working?")
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"GenAI Error: {e}")
