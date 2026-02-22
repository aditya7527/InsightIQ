"""Find exact error messages and working models."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings
import google.generativeai as genai

genai.configure(api_key=settings.gemini_api_key)

models_to_try = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-pro",
]

print("=== MODEL TESTS ===")
for model_name in models_to_try:
    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(
            'Say only: ok',
            generation_config=genai.types.GenerationConfig(max_output_tokens=10, temperature=0.0)
        )
        print(f"OK  {model_name}: '{resp.text.strip()}'")
    except Exception as e:
        # Print full error
        print(f"ERR {model_name}:")
        print(f"    {type(e).__name__}: {str(e)}")
        print()

print("=== LISTED MODELS ===")
try:
    names = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            names.append(m.name)
    for n in names:
        print(f"  {n}")
except Exception as e:
    print("list_models failed:", e)
