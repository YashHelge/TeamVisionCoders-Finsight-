"""
Fraud Detector — Phishing/spam pattern matching and statistical anomaly scoring.

anomaly_score = sigmoid(
    0.35 × normalize(z_amount) +
    0.25 × normalize(debit_burst_in_1h) +
    0.25 × merchant_novelty +
    0.15 × time_of_day_rarity
)

Score > 0.85 → push notification alert to user.
"""

import re
import math
import logging
from typing import Optional

logger = logging.getLogger("finsight.pipeline.fraud")

# ── Phishing patterns ──
PHISHING_INDICATORS = [
    (r'(?:lottery|lucky\s*draw|jackpot)', 'lottery_scam'),
    (r'(?:congratulations?|congrats).*(?:won|win|winner|selected)', 'prize_scam'),
    (r'(?:claim|collect)\s*(?:your\s*)?(?:prize|reward|money)', 'claim_scam'),
    (r'(?:KYC|kyc)\s*(?:expir|suspend|block|updat|verif)', 'fake_kyc'),
    (r'(?:account|card)\s*(?:will\s*be\s*)?(?:blocked|suspended|frozen|deactivat)', 'block_threat'),
    (r'(?:bit\.ly|tinyurl|goo\.gl|t\.co|short\.link|is\.gd)', 'suspicious_link'),
    (r'(?:click\s*(?:here|below|link)\s*(?:to|for))', 'phishing_link'),
    (r'(?:verify|update)\s*(?:your\s*)?(?:account|card|bank)\s*(?:details|info)', 'info_theft'),
    (r'(?:earn|make)\s*(?:Rs\.?|₹)?\s*\d+.*(?:per\s*day|daily|from\s*home)', 'money_scam'),
    (r'(?:share\s*(?:your\s*)?(?:OTP|PIN|CVV|password))', 'otp_theft'),
]

# ── Fake bank sender patterns ──
FAKE_SENDER_PATTERNS = [
    r'^\+?\d{10,}$',  # Phone numbers pretending to be banks
    r'(?:BANK|bank)\d{2,}',  # Generic bank references
]


def compute_fraud_score(text: str, sender: str = "") -> float:
    """
    Compute a fraud probability score based on phishing patterns.
    
    Returns: 0.0 (safe) to 1.0 (definitely fraudulent)
    """
    if not text:
        return 0.0

    score = 0.0
    detections = []

    # Check phishing indicators
    for pattern, label in PHISHING_INDICATORS:
        if re.search(pattern, text, re.IGNORECASE):
            score += 0.3
            detections.append(label)

    # Check fake sender
    for pattern in FAKE_SENDER_PATTERNS:
        if re.match(pattern, sender):
            score += 0.15
            detections.append('suspicious_sender')

    # Multiple exclamation marks (spam signal)
    if text.count('!') > 3:
        score += 0.1
        detections.append('exclamation_spam')

    # ALL CAPS text (spam signal)
    upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if upper_ratio > 0.6 and len(text) > 20:
        score += 0.1
        detections.append('caps_spam')

    # Urgency language
    if re.search(r'(?:urgent|immediately|within\s*\d+\s*hours?|last\s*chance)', text, re.IGNORECASE):
        score += 0.15
        detections.append('urgency')

    # Cap at 1.0
    score = min(score, 1.0)

    if detections:
        logger.info("Fraud signals detected: %s (score=%.2f)", detections, score)

    return round(score, 4)


def _sigmoid(x: float) -> float:
    """Sigmoid activation."""
    return 1.0 / (1.0 + math.exp(-x))


async def compute_anomaly_score(
    db_pool,
    user_id: str,
    amount: float,
    merchant: str,
    timestamp_hour: Optional[int] = None,
) -> float:
    """
    Compute statistical anomaly score for a transaction.
    
    anomaly_score = sigmoid(
        0.35 × normalize(z_amount) +
        0.25 × normalize(debit_burst_in_1h) +
        0.25 × merchant_novelty +
        0.15 × time_of_day_rarity
    )
    """
    if not db_pool:
        return 0.0

    try:
        async with db_pool.acquire() as conn:
            # z-score of amount relative to user's history
            stats = await conn.fetchrow(
                """SELECT AVG(amount) as avg_amt, STDDEV(amount) as std_amt
                FROM transactions 
                WHERE user_id = $1 AND direction = 'debit'""",
                user_id,
            )

            z_amount = 0.0
            if stats and stats["std_amt"] and stats["std_amt"] > 0:
                z_amount = abs((amount - float(stats["avg_amt"])) / float(stats["std_amt"]))

            # Debit burst: count of debits in the last hour
            burst_count = await conn.fetchval(
                """SELECT COUNT(*) FROM transactions
                WHERE user_id = $1 AND direction = 'debit'
                AND transaction_date >= NOW() - INTERVAL '1 hour'""",
                user_id,
            )
            debit_burst = min(burst_count / 10.0, 1.0)  # Normalize: 10+ debits/hour = 1.0

            # Merchant novelty: has user transacted with this merchant before?
            merchant_count = await conn.fetchval(
                """SELECT COUNT(*) FROM transactions
                WHERE user_id = $1 AND merchant = $2""",
                user_id, merchant,
            )
            merchant_novelty = 1.0 if merchant_count == 0 else max(0.0, 1.0 - merchant_count / 10.0)

            # Time of day rarity
            from datetime import datetime
            hour = timestamp_hour if timestamp_hour is not None else datetime.now().hour
            # Transactions between 12am-5am are unusual
            time_rarity = 0.0
            if hour < 5 or hour > 23:
                time_rarity = 0.8
            elif hour < 7:
                time_rarity = 0.4

            # Weighted anomaly score
            raw_score = (
                0.35 * min(z_amount / 3.0, 1.0) +   # Normalize z-score: 3σ = 1.0
                0.25 * debit_burst +
                0.25 * merchant_novelty +
                0.15 * time_rarity
            )

            anomaly_score = _sigmoid(raw_score * 4 - 2)  # Scale to sigmoid range

            return round(anomaly_score, 4)

    except Exception as e:
        logger.warning("Anomaly scoring failed: %s", e)
        return 0.0


def should_alert(anomaly_score: float, fraud_score: float) -> bool:
    """Determine if the user should be alerted about this transaction."""
    return anomaly_score > 0.85 or fraud_score > 0.70
