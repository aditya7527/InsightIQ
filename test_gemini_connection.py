import sys
import os

# Add parent dir to path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai.gpt_service import query_gpt
import logging
from app.core.config import settings

# Configure logging to see the fallback warnings
logging.basicConfig(level=logging.INFO)

print(f"Testing query_gpt with Key: {str(settings.gemini_api_key)[:5]}...")

try:
    print("Sending request...")
    response = query_gpt("Hello, are you working?", max_tokens=50)
    print("\n--- Response ---")
    print(response)
    print("--- Success ---")
except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
