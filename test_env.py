from dotenv import load_dotenv
import os

load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")
print(f"OPENROUTER_API_KEY found: {'Yes' if key else 'No'}")
if key:
    print(f"Key preview: {key[:10]}...")
