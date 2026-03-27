"""
Recommender — Groq Llama 3.3 70B structured JSON Cancel & Save recommendations.
"""

import json
import logging
from typing import Dict, List

logger = logging.getLogger("finsight.subscription.recommender")


async def generate_recommendations(
    subscriptions: List[Dict],
    top_n: int = 5,
) -> List[Dict]:
    """
    Generate Cancel & Save recommendations using Groq.
    
    Returns structured recommendations with:
    - recommendation (cancel/keep/downgrade)
    - rationale
    - alternatives
    - estimated_12m_saving
    - action_priority (high/medium/low)
    """
    if not subscriptions:
        return []

    from subscription.savings import compute_savings
    ranked = compute_savings(subscriptions)
    candidates = ranked[:top_n]

    if not candidates:
        return []

    # Try Groq for rich recommendations
    try:
        from groq_client import complete_json

        sub_summary = json.dumps([
            {
                "merchant": s["merchant"],
                "category": s.get("category", "Other"),
                "monthly_cost": s.get("monthly_cost", 0),
                "annual_cost": s.get("annual_cost", 0),
                "usage_score": s.get("usage_score", 0),
                "waste_score": s.get("waste_score", 0),
                "occurrence_count": s.get("occurrence_count", 0),
                "periodicity_days": s.get("periodicity_days", 30),
            }
            for s in candidates
        ], indent=2)

        prompt = f"""Analyze these subscriptions for an Indian user and provide Cancel & Save recommendations.

Subscriptions:
{sub_summary}

For each subscription, provide a JSON array with objects containing:
- "merchant": exact merchant name
- "recommendation": "cancel" | "keep" | "downgrade"
- "rationale": brief reason (1-2 sentences)
- "alternatives": list of cheaper/free alternatives
- "estimated_12m_saving": annual saving in INR if cancelled/downgraded
- "action_priority": "high" | "medium" | "low"

Focus on subscriptions with high waste_score (low usage relative to cost).
Consider Indian market alternatives. Be practical and specific.

Respond ONLY with the JSON array, no other text."""

        response = await complete_json(prompt)

        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and "recommendations" in response:
            return response["recommendations"]

    except Exception as e:
        logger.warning("Groq recommendation failed: %s — generating local recommendations", e)

    # Fallback: generate recommendations locally
    return _generate_local_recommendations(candidates)


def _generate_local_recommendations(subscriptions: List[Dict]) -> List[Dict]:
    """Generate simple recommendations without Groq."""
    recommendations = []

    for sub in subscriptions:
        waste = sub.get("waste_score", 0)
        usage = sub.get("usage_score", 0)
        monthly = sub.get("monthly_cost", 0)
        merchant = sub.get("merchant", "Unknown")

        if usage < 0.3 and waste > 100:
            rec = "cancel"
            priority = "high"
            rationale = f"Low usage ({usage:.0%}) with ₹{monthly:.0f}/month cost suggests this subscription is underutilized."
            saving = round(monthly * 12, 2)
        elif usage < 0.5:
            rec = "downgrade"
            priority = "medium"
            rationale = f"Moderate usage ({usage:.0%}). Consider downgrading to a lower plan."
            saving = round(monthly * 6, 2)
        else:
            rec = "keep"
            priority = "low"
            rationale = f"Good usage ({usage:.0%}). This subscription appears well-utilized."
            saving = 0

        # Indian market alternatives
        alternatives = _get_alternatives(merchant, sub.get("category", "Other"))

        recommendations.append({
            "merchant": merchant,
            "recommendation": rec,
            "rationale": rationale,
            "alternatives": alternatives,
            "estimated_12m_saving": saving,
            "action_priority": priority,
        })

    return recommendations


def _get_alternatives(merchant: str, category: str) -> List[str]:
    """Suggest Indian market alternatives."""
    alternatives_map = {
        "Netflix": ["JioCinema (free with Jio)", "Disney+ Hotstar (₹149/m)", "YouTube (free)"],
        "Spotify": ["YouTube Music (free tier)", "Gaana (free)", "Wynk Music (free with Airtel)"],
        "Amazon Prime": ["Flipkart Plus (free)", "JioCinema (free)"],
        "YouTube Premium": ["YouTube Vanced (free)", "Newpipe (free)"],
        "Disney+ Hotstar": ["JioCinema (free with Jio)", "YouTube (free)"],
        "OpenAI": ["Google Gemini (free tier)", "Claude (free tier)"],
        "Swiggy One": ["Zomato Pro (compare pricing)", "cook at home"],
        "Zomato Pro": ["Swiggy One (compare pricing)", "cook at home"],
    }

    alts = alternatives_map.get(merchant, [])
    if not alts:
        category_alts = {
            "Entertainment": ["Free streaming on YouTube", "JioCinema free tier"],
            "SaaS": ["Open source alternatives", "Free tier options"],
            "Food": ["Cook at home", "Local restaurants"],
            "Telecom": ["Compare plans on Jio, Airtel, Vi"],
        }
        alts = category_alts.get(category, ["Compare similar services for better pricing"])

    return alts
