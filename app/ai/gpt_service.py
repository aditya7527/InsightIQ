"""
AI/LLM Service — Google Gemini (primary) + Groq (fallback)
Provides query_gpt() and generate_insights_text() for all AI features.
"""
import os
import json
import time
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _key(env_name: str, settings_name: str) -> str | None:
    """Read API key from env or pydantic settings."""
    return os.getenv(env_name) or getattr(settings, settings_name, None)

# ── Lazy imports to avoid import-time crashes ──
_gemini_model = None
_groq_client = None


def _get_gemini():
    """Initialize Gemini model (lazy)."""
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai
        api_key = _key('GEMINI_API_KEY', 'gemini_api_key')
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


def _get_groq():
    """Initialize Groq client as fallback (lazy)."""
    global _groq_client
    if _groq_client is None:
        api_key = _key('GROQ_API_KEY', 'groq_api_key')
        if not api_key:
            return None
        try:
            from openai import OpenAI
            _groq_client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
        except Exception:
            return None
    return _groq_client


def _call_gemini(prompt: str, max_tokens: int, temperature: float) -> str:
    """Call Gemini API."""
    import google.generativeai as genai
    model = _get_gemini()
    if not model:
        raise RuntimeError("No Gemini API key")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
    )
    return response.text.strip()


def _call_groq(prompt: str, max_tokens: int, temperature: float) -> str:
    """Call Groq API as fallback."""
    client = _get_groq()
    if not client:
        raise RuntimeError("No Groq API key")
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def query_gpt(prompt: str, max_tokens: int = 1000, temperature: float = 0.2) -> str:
    """
    Query LLM: tries Gemini first, falls back to Groq on error.
    Name kept as query_gpt() for backward compatibility.
    """
    # Try Gemini first (with one retry on rate limit)
    for attempt in range(2):
        try:
            return _call_gemini(prompt, max_tokens, temperature)
        except Exception as e:
            err = str(e)
            if '429' in err and attempt == 0:
                logger.warning("Gemini rate limited, retrying in 4s...")
                time.sleep(4)
                continue
            logger.warning(f"Gemini failed: {err}, trying Groq fallback...")
            break

    # Fallback to Groq
    try:
        return _call_groq(prompt, max_tokens, temperature)
    except Exception as e2:
        logger.error(f"Both Gemini and Groq failed: {e2}")
        return f"Error: AI service unavailable. {str(e2)}"


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
