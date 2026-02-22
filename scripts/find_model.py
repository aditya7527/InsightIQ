import google.generativeai as genai
from app.core.config import settings
genai.configure(api_key=settings.gemini_api_key)

models_to_try = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.0-pro",
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro"
]

for m_name in models_to_try:
    try:
        print(f"Trying {m_name}...")
        model = genai.GenerativeModel(m_name)
        response = model.generate_content("Say hi", request_options={"timeout": 10.0})
        print(f"  Result: {response.text[:20]}")
        break
    except Exception as e:
        print(f"  Error: {e}")
