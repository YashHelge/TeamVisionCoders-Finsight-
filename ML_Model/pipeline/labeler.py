"""
Rule-Based Labeler — Weak supervision for Indian banking SMS.

Classifies into: financial_transaction, financial_alert, otp, promotional, personal, spam
Uses domain rules: sender patterns, amount regex, payment rail indicators,
OTP markers, promotional language, phishing signals.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("finsight.pipeline.labeler")

# ── Classification categories ──
CATEGORIES = [
    'financial_transaction',
    'financial_alert',
    'otp',
    'promotional',
    'personal',
    'spam',
]

# ── Sender-based rules ──
BANK_SHORTCODE_PATTERN = re.compile(r'^[A-Z]{2,8}$')  # Bank shortcodes are uppercase alpha
PHONE_NUMBER_PATTERN = re.compile(r'^\+?\d{10,13}$')

# ── Transaction indicators (high confidence) ──
TRANSACTION_PATTERNS = [
    (re.compile(r'(?:debited|credited)\s*(?:with\s*)?(?:Rs\.?|INR|₹)\s*[0-9,]+', re.IGNORECASE), 0.95),
    (re.compile(r'(?:Rs\.?|INR|₹)\s*[0-9,]+(?:\.[0-9]{1,2})?\s*(?:debited|credited|paid|received)', re.IGNORECASE), 0.95),
    (re.compile(r'(?:sent|received|paid|transferred)\s*(?:Rs\.?|INR|₹)\s*[0-9,]+', re.IGNORECASE), 0.90),
    (re.compile(r'UPI\s*(?:transaction|txn|payment)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:NEFT|IMPS|RTGS)\s*(?:of|for)?\s*(?:Rs\.?|INR|₹)\s*[0-9,]+', re.IGNORECASE), 0.95),
    (re.compile(r'(?:balance|bal)[:\s]*(?:Rs\.?|INR|₹)?\s*[0-9,]+.*(?:debited|credited)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:card|credit\s*card|debit\s*card)\s*(?:ending|no\.?|xx)\s*\d{4}', re.IGNORECASE), 0.85),
    (re.compile(r'(?:purchase|POS|ATM|withdrawal)\s*(?:of|for)?\s*(?:Rs\.?|INR|₹)', re.IGNORECASE), 0.90),
    (re.compile(r'EMI\s*(?:of\s*)?(?:Rs\.?|INR|₹)\s*[0-9,]+', re.IGNORECASE), 0.90),
]

# ── Financial alert patterns (not a transaction but financially relevant) ──
ALERT_PATTERNS = [
    (re.compile(r'(?:low\s*balance|minimum\s*balance|insufficient\s*fund)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:statement|e-?statement|account\s*summary)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:interest\s*(?:credited|debited)|dividend)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:loan|emi)\s*(?:due|overdue|reminder)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:premium|insurance)\s*(?:due|renewal)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:salary|pension)\s*(?:credited|received)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:FD|fixed\s*deposit|RD|recurring\s*deposit)\s*(?:mature|renew)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:credit\s*score|cibil|credit\s*limit)', re.IGNORECASE), 0.80),
]

# ── OTP patterns ──
OTP_PATTERNS = [
    (re.compile(r'\b(?:OTP|one[- ]?time[- ]?password)\s*(?:is|:)?\s*\d{4,8}', re.IGNORECASE), 0.98),
    (re.compile(r'\d{4,8}\s*is\s*(?:your\s*)?(?:OTP|verification\s*code|secure\s*code)', re.IGNORECASE), 0.98),
    (re.compile(r'(?:verify|confirm|authenticate)\s*(?:using|with)\s*(?:OTP|code)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:valid\s*for|expires?\s*in)\s*\d+\s*(?:min|minute|sec|hour)', re.IGNORECASE), 0.80),
    (re.compile(r'do\s*not\s*share\s*(?:this\s*)?(?:OTP|code|password)', re.IGNORECASE), 0.85),
]

# ── Promotional patterns ──
PROMOTIONAL_PATTERNS = [
    (re.compile(r'(?:cashback|cash\s*back)\s*(?:of\s*)?(?:Rs\.?|₹|%)?\s*\d+', re.IGNORECASE), 0.85),
    (re.compile(r'(?:offer|discount|coupon|voucher|deal)\s*(?:of|worth|upto|on)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:limited\s*time|hurry|last\s*day|ending\s*soon)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:use\s*code|apply\s*code|promo\s*code)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:flat|extra|additional)\s*\d+%\s*off', re.IGNORECASE), 0.90),
    (re.compile(r'(?:reward\s*points?|loyalty\s*points?|coins?)\s*(?:earned|redeemed|expir)', re.IGNORECASE), 0.85),
    (re.compile(r'(?:unsubscribe|opt[- ]?out|stop\s*\d+|reply\s*stop)', re.IGNORECASE), 0.80),
    (re.compile(r'(?:download|install|update)\s*(?:the\s*)?(?:app|application)', re.IGNORECASE), 0.80),
    (re.compile(r'(?:T&C|terms?\s*(?:and|&)\s*conditions?)\s*apply', re.IGNORECASE), 0.80),
]

# ── Spam / Phishing patterns ──
SPAM_PATTERNS = [
    (re.compile(r'(?:lottery|lucky\s*draw|jackpot)\s*(?:winner|winning)', re.IGNORECASE), 0.95),
    (re.compile(r'(?:congratulations?|congrats)\s*.*\b(?:won|win|winner|selected)\b', re.IGNORECASE), 0.95),
    (re.compile(r'(?:claim|collect)\s*(?:your\s*)?(?:prize|reward|money)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:KYC|kyc)\s*(?:expir|suspend|block|updat|verif)\w*', re.IGNORECASE), 0.85),
    (re.compile(r'(?:account|card|banking)\s*(?:will\s*be\s*)?(?:blocked|suspended|frozen)', re.IGNORECASE), 0.80),
    (re.compile(r'(?:bit\.ly|tinyurl|goo\.gl|t\.co|short\.link)', re.IGNORECASE), 0.75),
    (re.compile(r'(?:earn|make)\s*(?:Rs\.?|₹)?\s*\d+[,\d]*\s*(?:per|daily|monthly|from\s*home)', re.IGNORECASE), 0.90),
    (re.compile(r'(?:loan|credit)\s*(?:approved|sanctioned|available)\s*(?:of\s*)?(?:Rs\.?|₹)', re.IGNORECASE), 0.75),
]


def rule_based_label(text: str, sender: str = "") -> Tuple[str, float]:
    """
    Apply rule-based classification using domain knowledge.
    
    Returns: (category, confidence)
    Confidence >= 0.80 → direct output (skip ML)
    Confidence <  0.80 → needs ML ensemble
    """
    if not text:
        return ('personal', 0.50)

    best_category = 'personal'
    best_confidence = 0.0

    # ── Check OTP first (highest priority) ──
    for pattern, conf in OTP_PATTERNS:
        if pattern.search(text):
            if conf > best_confidence:
                best_category = 'otp'
                best_confidence = conf

    if best_confidence >= 0.90:
        return (best_category, best_confidence)

    # ── Check spam/phishing ──
    spam_score = 0.0
    spam_count = 0
    for pattern, conf in SPAM_PATTERNS:
        if pattern.search(text):
            spam_score = max(spam_score, conf)
            spam_count += 1
    
    if spam_count >= 2 or spam_score >= 0.90:
        return ('spam', min(spam_score + 0.05 * spam_count, 1.0))

    # ── Check transactions (core financial events) ──
    txn_score = 0.0
    txn_count = 0
    for pattern, conf in TRANSACTION_PATTERNS:
        if pattern.search(text):
            txn_score = max(txn_score, conf)
            txn_count += 1

    # Boost confidence if multiple transaction signals
    if txn_count >= 2:
        txn_score = min(txn_score + 0.05, 1.0)

    # Bank shortcode sender boosts transaction confidence
    if BANK_SHORTCODE_PATTERN.match(sender) and txn_score > 0:
        txn_score = min(txn_score + 0.05, 1.0)

    if txn_score > best_confidence:
        best_category = 'financial_transaction'
        best_confidence = txn_score

    # ── Check financial alerts ──
    alert_score = 0.0
    for pattern, conf in ALERT_PATTERNS:
        if pattern.search(text):
            alert_score = max(alert_score, conf)

    if alert_score > best_confidence:
        best_category = 'financial_alert'
        best_confidence = alert_score

    # ── Check promotional ──
    promo_score = 0.0
    promo_count = 0
    for pattern, conf in PROMOTIONAL_PATTERNS:
        if pattern.search(text):
            promo_score = max(promo_score, conf)
            promo_count += 1

    if promo_count >= 2:
        promo_score = min(promo_score + 0.05, 1.0)

    if promo_score > best_confidence:
        best_category = 'promotional'
        best_confidence = promo_score

    # ── Default to personal if nothing matched ──
    if best_confidence < 0.50:
        # Phone number sender → likely personal
        if PHONE_NUMBER_PATTERN.match(sender):
            return ('personal', 0.75)
        return ('personal', 0.50)

    return (best_category, best_confidence)


def get_all_categories() -> list:
    """Return all valid category labels."""
    return CATEGORIES.copy()
