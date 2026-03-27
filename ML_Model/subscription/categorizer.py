"""
Subscription Categorizer — Groq Llama 3.3 70B zero-shot classification.
"""

import json
import logging
from typing import List, Optional

logger = logging.getLogger("finsight.subscription.categorizer")

CATEGORIES = [
    "Entertainment", "Utilities", "SaaS", "Health",
    "Finance", "Food", "Shopping", "Education",
    "Transport", "Telecom", "Insurance", "Other",
]

# Fast local categorization based on known patterns
LOCAL_CATEGORIES = {
    'Netflix': 'Entertainment', 'Spotify': 'Entertainment', 'Disney+ Hotstar': 'Entertainment',
    'YouTube Premium': 'Entertainment', 'Amazon Prime': 'Entertainment', 'Apple TV+': 'Entertainment',
    'JioCinema': 'Entertainment', 'SonyLIV': 'Entertainment', 'ZEE5': 'Entertainment',
    'Apple Music': 'Entertainment', 'Gaana': 'Entertainment', 'Wynk Music': 'Entertainment',
    'Audible': 'Entertainment', 'YouTube Music': 'Entertainment',
    'OpenAI': 'SaaS', 'GitHub': 'SaaS', 'GitHub Copilot': 'SaaS',
    'Notion': 'SaaS', 'Canva': 'SaaS', 'Figma': 'SaaS',
    'Google One': 'SaaS', 'Google Workspace': 'SaaS',
    'Microsoft 365': 'SaaS', 'Apple iCloud': 'SaaS',
    'Dropbox': 'SaaS', 'Zoom': 'SaaS', 'Slack': 'SaaS',
    'Grammarly': 'SaaS',
    'Jio': 'Telecom', 'Jio Fiber': 'Telecom', 'Airtel': 'Telecom',
    'Vi': 'Telecom', 'BSNL': 'Telecom', 'ACT Fibernet': 'Telecom',
    'Swiggy': 'Food', 'Swiggy One': 'Food', 'Zomato': 'Food',
    'Zomato Pro': 'Food', 'BigBasket': 'Food', 'Blinkit': 'Food',
    'Amazon': 'Shopping', 'Flipkart': 'Shopping', 'Myntra': 'Shopping',
    'cult.fit': 'Health', 'Practo': 'Health', 'PharmEasy': 'Health',
    'Uber': 'Transport', 'Ola': 'Transport', 'Rapido': 'Transport',
    'CRED': 'Finance', 'Paytm': 'Finance',
    'LIC': 'Insurance', 'Star Health': 'Insurance', 'HDFC ERGO': 'Insurance',
    'Unacademy': 'Education', "BYJU'S": 'Education', 'Coursera': 'Education',
    'Udemy': 'Education',
    'Electricity Bill': 'Utilities', 'Tata Power': 'Utilities',
    'Water Bill': 'Utilities', 'Gas Bill': 'Utilities',
}


def categorize_local(merchant: str) -> Optional[str]:
    """Fast local categorization from known mapping."""
    return LOCAL_CATEGORIES.get(merchant)


async def categorize_with_groq(merchants: List[str]) -> dict:
    """
    Categorize merchants using Groq Llama 3.3 70B zero-shot.
    Returns: {merchant: category}
    """
    # First, resolve locally
    results = {}
    unknown = []

    for m in merchants:
        local_cat = categorize_local(m)
        if local_cat:
            results[m] = local_cat
        else:
            unknown.append(m)

    if not unknown:
        return results

    # Use Groq for unknown merchants
    try:
        from groq_client import complete_json

        prompt = f"""Categorize each merchant/service into exactly one category.

Categories: {', '.join(CATEGORIES)}

Merchants to categorize:
{json.dumps(unknown)}

Respond with a JSON object mapping merchant name to category.
Example: {{"Netflix": "Entertainment", "Jio": "Telecom"}}"""

        response = await complete_json(prompt)
        if isinstance(response, dict):
            results.update(response)

    except Exception as e:
        logger.warning("Groq categorization failed: %s — using 'Other'", e)
        for m in unknown:
            results[m] = "Other"

    # Ensure all merchants have categories
    for m in merchants:
        if m not in results:
            results[m] = "Other"

    return results
