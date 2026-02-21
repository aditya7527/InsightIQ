"""
AI/LLM Service — Google Gemini Only
Provides query_gpt() and generate_insights_text() for all AI features.
"""
import os
import json
import logging
import time
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Fallback Model List ──
# Priority order: Newest Flash -> General Flash -> Newest Pro -> General Pro
FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.5-pro-latest",
    "gemini-pro-latest"
]

def query_gpt(prompt: str, max_tokens: int = 1000, temperature: float = 0.2) -> str:
    """
    Query LLM with Model Fallback & Retries.
    Tries multiple models if one is rate-limited or unavailable.
    """
    if not settings.gemini_api_key:
        logger.error("Gemini API key is missing.")
        return "Error: AI service unavailable. Missing API Key."

    genai.configure(api_key=settings.gemini_api_key)

    last_error = ""

    for model_name in FALLBACK_MODELS:
        try:
            # Configure model
            model = genai.GenerativeModel(model_name)
            
            # Attempt generation with retries for transient errors
            for attempt in range(2): 
                try:
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=max_tokens,
                            temperature=temperature,
                        )
                    )
                    # If successful, return immediately
                    if response.text:
                        return response.text.strip()
                except Exception as e:
                    err_msg = str(e)
                    # If quota exceeded (429), break inner retry loop to try next MODEL
                    if '429' in err_msg or 'Resource exhausted' in err_msg:
                        logger.warning(f"Model {model_name} rate limited (429). Switching model...")
                        break 
                    
                    # For other errors, maybe retry same model once
                    time.sleep(1)
                    last_error = f"{model_name}: {e}"
        
        except Exception as e:
            logger.error(f"Failed to initialize model {model_name}: {e}")
            last_error = str(e)
            continue

    logger.error(f"All AI models failed. Last error: {last_error}")
    return "Error: AI service temporarily unavailable (Rate Limit or Quota Exceeded)."


def generate_insights_text(analysis_payload: dict) -> dict:
    """Generate structured insights from analytics data."""
    prompt = (
        "You are a senior business analyst. Given the following analytics results, "
        "produce a JSON object with keys: summary, kpis, risks, recommendations.\n"
        f"Analytics: {json.dumps(analysis_payload, default=str)[:3000]}\n"
        "Return ONLY valid JSON, no markdown, no code fences, no explanation."
    )
    try:
        raw = query_gpt(prompt, max_tokens=500, temperature=0.2)
        
        if raw.startswith("Error:"):
            return {"summary": "AI service temporarily unavailable.", "kpis": [], "risks": [], "recommendations": [], "error": raw}

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        # Extract JSON
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(cleaned[start:end])
        return {"summary": raw, "kpis": [], "risks": [], "recommendations": []}
    except Exception as e:
        logger.error(f"Insights generation error: {e}")
        return {"summary": "", "kpis": [], "risks": [], "recommendations": [], "error": str(e)}
