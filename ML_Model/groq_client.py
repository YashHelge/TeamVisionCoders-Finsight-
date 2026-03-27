"""
Groq Client — Llama 3.3 70B streaming chat with circuit breaker and semantic cache.
"""

import hashlib
import json
import logging
import time
from typing import AsyncGenerator, List, Optional

from config import settings

logger = logging.getLogger("finsight.groq_client")

# ── Circuit Breaker State ──
_failure_count = 0
_last_failure_time = 0.0
_circuit_open = False
CB_THRESHOLD = 3
CB_RESET_SECONDS = 60


class GroqCircuitOpen(Exception):
    """Raised when the Groq circuit breaker is open."""
    pass


def _check_circuit():
    """Check if circuit breaker is open."""
    global _circuit_open, _failure_count, _last_failure_time

    if _circuit_open:
        if time.time() - _last_failure_time > CB_RESET_SECONDS:
            # Half-open: allow one attempt
            _circuit_open = False
            _failure_count = 0
            logger.info("Groq circuit breaker half-open — allowing probe request")
        else:
            raise GroqCircuitOpen("Groq service temporarily unavailable (circuit open)")


def _record_failure():
    global _failure_count, _last_failure_time, _circuit_open
    _failure_count += 1
    _last_failure_time = time.time()
    if _failure_count >= CB_THRESHOLD:
        _circuit_open = True
        logger.warning("Groq circuit breaker OPEN after %d failures", _failure_count)


def _record_success():
    global _failure_count, _circuit_open
    _failure_count = 0
    _circuit_open = False


async def stream_chat(messages: List[dict]) -> AsyncGenerator[str, None]:
    """Stream chat completion from Groq Llama 3.3 70B."""
    _check_circuit()

    if not settings.GROQ_API_KEY:
        yield "Groq API key not configured. Please set GROQ_API_KEY in your environment."
        return

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        stream = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            stream=True,
            max_tokens=4096,
            temperature=0.7,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                _record_success()
                yield chunk.choices[0].delta.content

    except GroqCircuitOpen:
        raise
    except Exception as e:
        _record_failure()
        logger.error("Groq streaming error: %s", e)
        yield f"AI service error: {str(e)}"


async def complete_json(prompt: str) -> Optional[dict]:
    """Get a JSON response from Groq (non-streaming)."""
    _check_circuit()

    if not settings.GROQ_API_KEY:
        logger.warning("Groq API key not configured")
        return None

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a JSON API. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        _record_success()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}|\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            logger.warning("Failed to parse Groq JSON response")
            return None

    except GroqCircuitOpen:
        raise
    except Exception as e:
        _record_failure()
        logger.error("Groq completion error: %s", e)
        return None


# ── Semantic Cache ──

def _cache_key(user_id: str, query: str) -> str:
    """Generate semantic cache key."""
    normalized = query.lower().strip()
    hash_val = hashlib.md5(normalized.encode()).hexdigest()[:16]
    return f"groq_cache:{user_id}:{hash_val}"


async def check_semantic_cache(redis_client, user_id: str, query: str) -> Optional[str]:
    """Check if a similar query has been cached."""
    if not redis_client:
        return None

    try:
        key = _cache_key(user_id, query)
        cached = await redis_client.get(key)
        if cached:
            logger.debug("Semantic cache hit for user %s", user_id)
            return cached
    except Exception:
        pass

    return None


async def cache_response(redis_client, user_id: str, query: str, response: str):
    """Cache a query-response pair."""
    if not redis_client or not response:
        return

    try:
        key = _cache_key(user_id, query)
        await redis_client.setex(key, settings.GROQ_CACHE_TTL, response)
    except Exception:
        pass
