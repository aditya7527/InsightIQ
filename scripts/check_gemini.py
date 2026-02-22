from app.core.config import settings
print(f"API Key present: {bool(settings.gemini_api_key)}")
if settings.gemini_api_key:
    # Print first and last 4 chars
    key = settings.gemini_api_key
    print(f"Key format: {key[:4]}...{key[-4:]}")

import google.generativeai as genai
try:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("test")
    print(f"Direct Gemini test: {response.text[:50]}")
except Exception as e:
    print(f"Direct Gemini error: {e}")
