
import os
import sys
import traceback
from dotenv import load_dotenv

# Force ASCII output for Windows
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='ascii', errors='replace')

# Add project root to sys.path
sys.path.append(os.getcwd())

# Force load .env
load_dotenv(".env", override=True)

from app.ai.gpt_service import _get_groq, _call_groq, _key

def test_groq():
    print("=== Groq Integration Test (ASCII) ===")
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[FAIL] GROQ_API_KEY not found in environment!")
        return
    
    mask = api_key[:7] + "..." + api_key[-4:]
    print(f"Detected Key in Script: {mask}")
    
    try:
        print("Checking internal _key detection...")
        internal_key = _key('GROQ_API_KEY', 'groq_api_key')
        print(f"Internal _key detection: {internal_key[:7] if internal_key else 'None'}")

        print("Checking _get_groq() output...")
        client = _get_groq()
        if not client:
            print("[FAIL] _get_groq() returned None.")
            
            print("Attempting manual OpenAI initialization for debugging...")
            from openai import OpenAI
            try:
                dbg_client = OpenAI(
                    api_key=internal_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                print("[INFO] Manual OpenAI init succeeded (unexpectedly).")
            except Exception as e:
                print(f"[ERROR] Manual OpenAI init failed: {e}")
                traceback.print_exc()
            return
            
        print("Sending test prompt to Groq...")
        response = _call_groq("Hello, who are you?", max_tokens=20, temperature=0.2)
        print(f"[SUCCESS] Groq Response: {response}")
        print("\nIntegration looks healthy!")
        
    except Exception as e:
        print(f"[ERROR] Exception during test: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_groq()
