import google.generativeai as genai
from app.core.config import settings
import time

genai.configure(api_key=settings.gemini_api_key)

models_to_test = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.0-pro"
]

for m in models_to_test:
    try:
        print(f"Testing {m}...")
        model = genai.GenerativeModel(m)
        res = model.generate_content("hello", request_options={"timeout": 10.0})
        print(f"  SUCCESS: {res.text[:10]}")
        exit(0)
    except Exception as e:
        print(f"  FAILED {m}: {e}")
        time.sleep(1)

print("All models failed.")
exit(1)
