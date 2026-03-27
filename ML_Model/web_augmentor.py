"""
Web Augmentor — Real-time web search augmentation for AI chat.
Provides current financial news, product info, and policy details.
"""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger("finsight.web_augmentor")

# DuckDuckGo Instant Answers API (no key needed)
DDG_API = "https://api.duckduckgo.com/"


async def augment_query(query: str, max_results: int = 3) -> str:
    """
    Augment a user query with web search results.
    Uses DuckDuckGo Instant Answers API (free, no API key required).
    
    Returns: formatted context string for injection into AI prompt.
    """
    if not query:
        return ""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            }
            response = await client.get(DDG_API, params=params)
            data = response.json()

        results = []

        # Abstract (main answer)
        if data.get("Abstract"):
            results.append(f"Summary: {data['Abstract']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text']}")

        # Answer (instant answer if available)
        if data.get("Answer"):
            results.append(f"Answer: {data['Answer']}")

        if results:
            return "\n".join(results)

    except Exception as e:
        logger.warning("Web augmentation failed: %s", e)

    return ""


async def search_financial_news(topic: str) -> str:
    """Search for recent financial news related to a topic."""
    query = f"{topic} India finance news"
    return await augment_query(query)


async def get_product_info(product: str) -> str:
    """Get product/service information for subscription recommendations."""
    query = f"{product} pricing plans India"
    return await augment_query(query)
