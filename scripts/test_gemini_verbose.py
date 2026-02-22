"""Test Gemini API with verbose error output."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
import google.generativeai as genai

print("API Key:", settings.gemini_api_key[:12] + "..." if settings.gemini_api_key else "MISSING")

genai.configure(api_key=settings.gemini_api_key)

# List available models
print("\nAvailable models:")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(" ", m.name)
except Exception as e:
    print("  Could not list models:", e)

# Try the model
print("\nTesting gemini-1.5-flash...")
try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(
        '{"status": "ok"}',
        generation_config=genai.types.GenerationConfig(max_output_tokens=20, temperature=0.0)
    )
    print("Response:", resp.text)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:400])
    traceback.print_exc()
