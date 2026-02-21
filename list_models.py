import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

with open("models.txt", "w") as f:
    try:
        f.write("Available Models:\n")
        for m in genai.list_models():
            f.write(f"Name: {m.name}\n")
            f.write(f"Methods: {m.supported_generation_methods}\n")
            f.write("-" * 20 + "\n")
    except Exception as e:
        f.write(f"Error listing models: {e}")
