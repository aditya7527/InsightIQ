"""
AI/LLM Service — Gemini & OpenRouter Integration
All AI features route through this module.
- Fast-fail on 429 (free tier rate limit) — never blocks the analytics pipeline
- Checks GEMINI_API_KEY, then OPENROUTER_API_KEY as fallback.
"""
import json
import logging
import time
import google.generativeai as genai
import requests
from typing import Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

_GEMINI_MODEL = "gemini-2.0-flash"
_OPENROUTER_MODEL = "google/gemini-2.0-flash-001"

# Track last 429 to implement per-session backoff without blocking
_last_rate_limit_ts: float = 0.0
_RATE_LIMIT_COOLDOWN = 30.0  # seconds: if we were 429'd recently, skip AI calls

def _is_rate_limited() -> bool:
    """Returns True if we were recently rate-limited (within cooldown window)."""
    return (time.monotonic() - _last_rate_limit_ts) > 0 and (time.monotonic() - _last_rate_limit_ts) < _RATE_LIMIT_COOLDOWN

# In-memory cache to save quota for identical prompts
_ai_cache: Dict[str, str] = {}
_MAX_CACHE_SIZE = 100

def _rate_limit_json() -> str:
    """Helper to generate a consistent rate-limit error JSON."""
    remaining = _RATE_LIMIT_COOLDOWN - (time.monotonic() - _last_rate_limit_ts)
    secs = int(remaining) if remaining > 1 else 1
    return json.dumps({"error": f"AI temporarily rate-limited. Analytics still work — try again in {secs} seconds."})

def query_gpt(prompt: str, max_tokens: int = 800, temperature: float = 0.2) -> str:
    """
    Query Google Gemini OR OpenRouter. Returns a string on success, or an error-JSON string.
    Includes simple in-memory caching to preserve API quota.
    """
    global _last_rate_limit_ts

    # 1. Check Cache
    cache_key = f"{prompt}_{max_tokens}_{temperature}"
    if cache_key in _ai_cache:
        logger.info("Serving AI response from cache.")
        return _ai_cache[cache_key]

    if not settings.gemini_api_key and not settings.openrouter_api_key:
        logger.warning("No AI keys configured.")
        return '{"error": "AI not configured — add GEMINI_API_KEY or OPENROUTER_API_KEY to .env"}'

    if _is_rate_limited():
        return _rate_limit_json()

    err_str = ""
    # ── Attempt 1: OpenRouter (if configured) ───────────────────────────────
    if settings.openrouter_api_key:
        try:
            logger.info("Attempting OpenRouter (%s)...", _OPENROUTER_MODEL)
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "InsightIQ",
                },
                json={
                    "model": _OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    text = data["choices"][0].get("message", {}).get("content", "").strip()
                    if text:
                        # Update cache
                        if len(_ai_cache) < _MAX_CACHE_SIZE:
                            _ai_cache[cache_key] = text
                        return text
            else:
                err_str = f"OpenRouter status {response.status_code}: {response.text}"
                logger.warning(err_str)
                if response.status_code == 429:
                    _trigger_rate_limit("OpenRouter")
                    return _rate_limit_json()
        
        except Exception as e:
            err_str = f"OpenRouter API exception: {str(e)}"
            logger.warning(err_str)

    # ── Attempt 2: Gemini Direct (if configured and Attempt 1 failed/skipped)
    if settings.gemini_api_key:
        try:
            logger.info("Attempting Native Gemini (%s)...", _GEMINI_MODEL)
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(_GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                ),
                request_options={"timeout": 10.0}
            )
            text = getattr(response, "text", None)
            if text:
                res_text = text.strip()
                # Update cache
                if len(_ai_cache) < _MAX_CACHE_SIZE:
                    _ai_cache[cache_key] = res_text
                return res_text
            return '{"error": "Gemini returned an empty response"}'
            
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "ResourceExhausted" in err_str or "quota" in err_str.lower():
                _trigger_rate_limit("Native Gemini")
                return _rate_limit_json()

            if "403" in err_str or "API_KEY" in err_str.upper():
                logger.error("Gemini API key rejected: %s", err_str[:200])
                return '{"error": "Invalid API key. Check GEMINI_API_KEY in .env"}'
            
            logger.error("Gemini native error: %s", err_str[:300])

    return '{"error": "AI calls failed — analytics pipeline unaffected."}'


def _trigger_rate_limit(source="AI"):
    global _last_rate_limit_ts
    _last_rate_limit_ts = time.monotonic()
    logger.warning("%s 429 rate-limit hit. AI calls paused for %ds.", source, _RATE_LIMIT_COOLDOWN)


def generate_insights_text(analysis_payload: dict) -> dict:
    """Generate structured business insights from analytics data."""
    prompt = (
        "You are a senior business analyst. Given analytics data, "
        "return a JSON object with keys: summary, kpis, risks, recommendations.\n"
        f"Data: {json.dumps(analysis_payload, default=str)[:2000]}\n"
        "Return ONLY valid JSON — no markdown, no code fences."
    )
    try:
        raw = query_gpt(prompt, max_tokens=500, temperature=0.2)

        # Strip markdown code fences if output is wrapped
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            end_idx = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "```"), len(lines))
            cleaned = "\n".join(lines[1:end_idx]).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(cleaned[start:end])
            if "error" in parsed:
                return {
                    "summary": "AI temporarily unavailable — analytics are still accurate.",
                    "kpis": [], "risks": [], "recommendations": [],
                    "error": parsed["error"],
                }
            return parsed

        return {"summary": raw, "kpis": [], "risks": [], "recommendations": []}

    except Exception as exc:
        logger.error("generate_insights_text error: %s", exc)
        return {
            "summary": "AI error generating insights.", "kpis": [], "risks": [], "recommendations": [],
            "error": str(exc),
        }
