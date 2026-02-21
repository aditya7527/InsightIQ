
import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

MODELS_TO_TEST = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-1.5-pro-latest"
]

print(f"Testing {len(MODELS_TO_TEST)} models for availability...\n")

for model_name in MODELS_TO_TEST:
    print(f"Testing model: {model_name}...")
    try:
        model = genai.GenerativeModel(model_name)
        # Use a very short prompt to minimize token usage
        response = model.generate_content("Hi", request_options={"timeout": 10})
        print(f"SUCCESS: {model_name} responded: {response.text.strip()[:20]}...")
    except Exception as e:
        print(f"FAILURE: {model_name} failed. Error: {e}")
    print("-" * 30)
    time.sleep(1) # Be nice to the API
