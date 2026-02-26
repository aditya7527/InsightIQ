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

# Track per-provider rate limits to allow failover
_last_429_openrouter: float = 0.0
_last_429_gemini: float = 0.0
_RATE_LIMIT_COOLDOWN = 30.0 

def _is_provider_limited(ts: float) -> bool:
    return (time.monotonic() - ts) < _RATE_LIMIT_COOLDOWN

# In-memory cache to save quota for identical prompts
_ai_cache: Dict[str, str] = {}
_MAX_CACHE_SIZE = 100

def _rate_limit_json() -> str:
    """Helper to generate a consistent rate-limit error JSON."""
    # Show the minimum remaining wait time across providers if both are down
    rem_or = max(0, _RATE_LIMIT_COOLDOWN - (time.monotonic() - _last_429_openrouter))
    rem_ge = max(0, _RATE_LIMIT_COOLDOWN - (time.monotonic() - _last_429_gemini))
    
    # If one is still available, this shouldn't be called, but as a fallback:
    secs = int(min(rem_or, rem_ge)) if (rem_or > 0 and rem_ge > 0) else 10
    return json.dumps({"error": f"AI temporarily rate-limited. Analytics still work — try again in {secs} seconds."})

def query_gpt(prompt: str, max_tokens: int = 800, temperature: float = 0.2) -> str:
    """
    Query OpenRouter with fallback to Native Gemini.
    Independent rate-limiting allows failover if one provider is exhausted.
    """
    global _last_429_openrouter, _last_429_gemini

    # 1. Check Cache
    cache_key = f"{prompt}_{max_tokens}_{temperature}"
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]

    if not settings.gemini_api_key and not settings.openrouter_api_key:
        return '{"error": "AI not configured — add GEMINI_API_KEY or OPENROUTER_API_KEY to .env"}'

    # ── Attempt 1: OpenRouter ─────────────────────────────────────────────
    if settings.openrouter_api_key and not _is_provider_limited(_last_429_openrouter):
        try:
            logger.info("Attempting OpenRouter...")
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
                text = response.json()["choices"][0]["message"]["content"].strip()
                if text:
                    if len(_ai_cache) < _MAX_CACHE_SIZE: _ai_cache[cache_key] = text
                    return text
            elif response.status_code == 429:
                logger.warning("OpenRouter 429 hit. Switching to fallback...")
                _last_429_openrouter = time.monotonic()
                # Continue to Gemini...
            else:
                logger.warning("OpenRouter error %d: %s", response.status_code, response.text)
        except Exception as e:
            logger.warning("OpenRouter exception: %s", e)

    # ── Attempt 2: Native Gemini (Fallback) ───────────────────────────────
    if settings.gemini_api_key and not _is_provider_limited(_last_429_gemini):
        try:
            logger.info("Attempting Native Gemini...")
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
                if len(_ai_cache) < _MAX_CACHE_SIZE: _ai_cache[cache_key] = res_text
                return res_text
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "ResourceExhausted" in err_str or "quota" in err_str.lower():
                logger.warning("Native Gemini 429 hit.")
                _last_429_gemini = time.monotonic()
            else:
                logger.error("Gemini error: %s", err_str[:300])

    return _rate_limit_json()


def _trigger_rate_limit(source="AI"):
    """Legacy helper for single-provider triggers (maintained for compat)"""
    global _last_429_openrouter, _last_429_gemini
    now = time.monotonic()
    if "OpenRouter" in source: _last_429_openrouter = now
    else: _last_429_gemini = now


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
