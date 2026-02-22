import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.gemini_api_key)

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        name = m.name
        try:
            print(f"Testing {name}...")
            model = genai.GenerativeModel(name)
            res = model.generate_content("hi", request_options={"timeout": 10.0})
            print(f"  SUCCESS! {res.text[:10]}")
        except Exception as e:
            print(f"  FAILED: {str(e)[:50]}")
