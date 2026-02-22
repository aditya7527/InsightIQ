"""Test the Gemini API integration — verifies the service works or gracefully degrades."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.gpt_service import query_gpt, _GEMINI_MODEL
from app.core.config import settings

print(f"Gemini model : {_GEMINI_MODEL}")
print(f"API key set  : {'YES (' + settings.gemini_api_key[:8] + '...)' if settings.gemini_api_key else 'NO'}")

import time
start = time.monotonic()
result = query_gpt(
    'Reply with valid JSON only: {"status": "ok", "message": "Gemini is working"}',
    max_tokens=60
)
elapsed = time.monotonic() - start

print(f"Response time: {elapsed:.2f}s (FAST-FAIL expected if rate-limited)")
print(f"Response     : {result[:300]}")

try:
    parsed = json.loads(result)
    if parsed.get("status") == "ok":
        print("Result: GEMINI AI IS FULLY WORKING")
    elif "error" in parsed:
        if "rate-limited" in parsed["error"].lower() or "quota" in parsed.get("error","").lower():
            print("Result: RATE LIMITED (expected on free tier) - fast-fail working correctly")
            print("        Analytics pipeline is NOT blocked (response in <1s)")
        elif "not configured" in parsed.get("error","").lower():
            print("Result: API KEY MISSING")
        else:
            print("Result: AI ERROR -", parsed["error"])
    print("JSON parse   : OK")
except Exception as e:
    print("JSON parse   : FAILED -", e)

print(f"\nFast-fail working: {'YES' if elapsed < 5 else 'NO - took too long'}")
