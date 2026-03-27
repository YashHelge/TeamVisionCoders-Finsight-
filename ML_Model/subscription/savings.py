"""
Savings Computer + Priority Ranker.

monthly_cost, annual_cost, usage_score,
waste_score = (1 - usage_score) × annual_cost
ranked by waste_score DESC
"""

import logging
from typing import Dict, List

logger = logging.getLogger("finsight.subscription.savings")


def compute_savings(subscriptions: List[Dict]) -> List[Dict]:
    """
    Compute savings metrics for each subscription.
    
    Input: list of subscription dicts with:
        - merchant, avg_monthly_cost, periodicity_days, occurrence_count,
          first_seen, last_seen, periodicity_score
    
    Adds: monthly_cost, annual_cost, usage_score, waste_score, priority_rank
    """
    result = []

    for sub in subscriptions:
        monthly_cost = sub.get("avg_monthly_cost", 0)
        period_days = sub.get("periodicity_days", 30)

        # Normalize to monthly cost
        if period_days > 0:
            daily_cost = monthly_cost / period_days
            monthly_normalized = daily_cost * 30
        else:
            monthly_normalized = monthly_cost

        annual_cost = monthly_normalized * 12

        # Usage score: how consistently the user uses this subscription
        # Based on: occurrence_count vs expected occurrences
        occurrence_count = sub.get("occurrence_count", 1)
        periodicity_score = sub.get("periodicity_score", 0.5)

        # Expected occurrences based on time range
        first_seen = sub.get("first_seen")
        last_seen = sub.get("last_seen")

        usage_score = _compute_usage_score(
            occurrence_count, period_days, first_seen, last_seen, periodicity_score
        )

        # Waste score = (1 - usage_score) × annual_cost
        waste_score = (1 - usage_score) * annual_cost

        enhanced = {**sub}
        enhanced["monthly_cost"] = round(monthly_normalized, 2)
        enhanced["annual_cost"] = round(annual_cost, 2)
        enhanced["usage_score"] = round(usage_score, 4)
        enhanced["waste_score"] = round(waste_score, 2)

        result.append(enhanced)

    # Rank by waste_score descending
    result.sort(key=lambda x: x.get("waste_score", 0), reverse=True)

    # Add priority rank
    for i, sub in enumerate(result):
        sub["priority_rank"] = i + 1

    return result


def _compute_usage_score(
    occurrence_count: int,
    period_days: int,
    first_seen,
    last_seen,
    periodicity_score: float,
) -> float:
    """
    Compute usage score (0.0 = completely unused, 1.0 = heavily used).
    
    Factors:
    - Regularity: how consistent the charges are
    - Recency: how recently the last charge occurred
    - Frequency: actual vs expected occurrence count
    """
    score = 0.0

    # Regularity from periodicity score
    score += 0.4 * periodicity_score

    # Frequency: actual occurrences vs expected
    if first_seen and last_seen and period_days > 0:
        from datetime import datetime

        if isinstance(first_seen, str):
            try:
                first_seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            except ValueError:
                first_seen = None
        if isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            except ValueError:
                last_seen = None

        if first_seen and last_seen:
            span_days = (last_seen - first_seen).days
            expected = max(span_days / period_days, 1)
            freq_ratio = min(occurrence_count / expected, 1.0)
            score += 0.3 * freq_ratio

            # Recency: days since last charge
            now = datetime.utcnow()
            if last_seen.tzinfo:
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)
            days_since = (now - last_seen).days
            recency = max(0, 1.0 - days_since / (period_days * 2))
            score += 0.3 * recency
        else:
            score += 0.3 * min(occurrence_count / 5.0, 1.0)
    else:
        score += 0.3 * min(occurrence_count / 5.0, 1.0)

    return min(max(score, 0.0), 1.0)


def get_top_savings(subscriptions: List[Dict], top_n: int = 5) -> List[Dict]:
    """Get the top N savings opportunities by waste_score."""
    ranked = compute_savings(subscriptions)
    return [
        {
            "merchant": s["merchant"],
            "monthly_cost": s.get("monthly_cost", 0),
            "annual_cost": s.get("annual_cost", 0),
            "waste_score": s.get("waste_score", 0),
            "usage_score": s.get("usage_score", 0),
            "priority_rank": s.get("priority_rank", 0),
        }
        for s in ranked[:top_n]
        if s.get("waste_score", 0) > 0
    ]
