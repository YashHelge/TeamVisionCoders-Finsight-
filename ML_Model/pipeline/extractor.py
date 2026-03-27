"""
Transaction Field Extractor — Converts classified financial signals
into structured transaction objects.
"""

import re
import logging
from typing import Dict, Optional
from datetime import datetime

from pipeline.preprocessor import (
    extract_amount, extract_balance, classify_direction,
    detect_payment_rail, detect_bank, ACCOUNT_PATTERN, UPI_REF_PATTERN,
)

logger = logging.getLogger("finsight.pipeline.extractor")

# ── Merchant extraction patterns (ordered by specificity, most specific first) ──
MERCHANT_PATTERNS = [
    # NCMC / Offline Wallet Prepaid card
    re.compile(r'(offline\s*wallet(?:.*?)(?:prepaid(?:.*?))?(?:card)?)', re.IGNORECASE),
    # "from PERSON NAME thru/via/through BANK" (UPI P2P)
    re.compile(r'(?:from|received\s+from)\s+([A-Za-z][A-Za-z\s]{2,40}?)\s+(?:thru|via|through)\b', re.IGNORECASE),
    # "to PERSON/MERCHANT" followed by various terminators
    re.compile(r'(?:paid\s+to|sent\s+to|transferred\s+to|to)\s+([A-Za-z][A-Za-z\s&.\'-]{2,40}?)\s*(?:\s+on\b|\s+via\b|\s+ref\b|\s+thru\b|\s+upi\b|\s+a/?c\b|\s+ac\b|\s+for\b|\.\s|$)', re.IGNORECASE),
    # "from PERSON/MERCHANT" followed by terminators
    re.compile(r'(?:from)\s+([A-Za-z][A-Za-z\s&.\'-]{2,40}?)\s*(?:\s+on\b|\s+ref\b|\s+upi\b|\s+a/?c\b|\.\s|$)', re.IGNORECASE),
    # "at MERCHANT" (POS transactions)
    re.compile(r'\bat\s+([A-Za-z][A-Za-z0-9\s&.\'-]{2,40}?)\s*(?:\s+on\b|\s+ref\b|\s+for\b|\.\s|,|$)', re.IGNORECASE),
    # VPA merchant@bank (UPI VPA)
    re.compile(r'VPA\s+([a-zA-Z0-9._-]+)@', re.IGNORECASE),
    # "trf to/from MERCHANT"
    re.compile(r'(?:trf|transfer)\s+(?:to|from)\s+([A-Za-z][A-Za-z0-9\s&.\'-]{2,40}?)(?:\s|$)', re.IGNORECASE),
    # "Info: UPI/CREDIT/REF.-BANK" → extract from the info field
    re.compile(r'Info[:\s]+UPI/(?:CREDIT|DEBIT)/(\d+)[.\s-]*([A-Z]+)', re.IGNORECASE),
    # "for PERIOD REFERENCE" (like "for 21CM17Y APB")
    re.compile(r'for\s+(\w+\s+[A-Z]{2,8})\b', re.IGNORECASE),
]

# Stopwords that should never be a merchant name
MERCHANT_STOPWORDS = {
    'you', 'your', 'dear', 'customer', 'user', 'sir', 'madam',
    'alert', 'notice', 'reminder', 'info', 'information',
    'the', 'this', 'that', 'with', 'has', 'been', 'was', 'are',
    'account', 'payment', 'transaction', 'amount', 'credited',
    'debited', 'balance', 'available', 'bank', 'card',
}


def extract_merchant(text: str) -> Optional[str]:
    """
    Extract merchant/sender name from SMS/notification text.
    Uses smart patterns for Indian banking SMS.
    """
    for pattern in MERCHANT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            # Filter out stopwords and too-short names
            if len(raw) < 2:
                continue
            first_word = raw.split()[0].lower()
            if first_word in MERCHANT_STOPWORDS:
                continue
            # Avoid entire SMS body fragments
            if len(raw) > 50:
                continue
            return normalize_merchant(raw)

    # ── Fallback: Try to extract a person name from common UPI patterns ──
    # "from NAME thru" or "received from NAME"
    fallback_match = re.search(
        r'(?:from|received\s+from)\s+([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){0,3})',
        text, re.IGNORECASE
    )
    if fallback_match:
        raw = fallback_match.group(1).strip()
        first_word = raw.split()[0].lower()
        if first_word not in MERCHANT_STOPWORDS and len(raw) > 2:
            return normalize_merchant(raw)

    # ── Fallback: Bank name from the SMS tail (e.g. "-SBI", "-IPPB") ──
    tail_match = re.search(r'-\s*([A-Z]{2,10})\s*$', text)
    if tail_match:
        bank_code = tail_match.group(1)
        # Check if this is a known bank
        from pipeline.preprocessor import BANK_SENDERS
        for code, bank_name in BANK_SENDERS.items():
            if code in bank_code or bank_code in code:
                return bank_name
        return bank_code

    return None


# ── Date patterns ──
DATE_PATTERNS = [
    re.compile(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'),
    re.compile(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{2,4})', re.IGNORECASE),
    re.compile(r'(\d{4}-\d{2}-\d{2})'),
]

# ── Merchant normalization aliases ──
MERCHANT_ALIASES = {
    'netflix': 'Netflix', 'netflix.com': 'Netflix', 'netflix india': 'Netflix',
    'spotify': 'Spotify', 'spotify india': 'Spotify', 'spotify ab': 'Spotify',
    'amazon': 'Amazon', 'amazon.in': 'Amazon', 'amzn': 'Amazon', 'amazon pay': 'Amazon Pay',
    'flipkart': 'Flipkart', 'flipkart internet': 'Flipkart',
    'swiggy': 'Swiggy', 'swiggy instamart': 'Swiggy Instamart',
    'zomato': 'Zomato', 'zomato ltd': 'Zomato', 'zomato hyperpure': 'Zomato',
    'uber': 'Uber', 'uber india': 'Uber', 'uber eats': 'Uber Eats',
    'ola': 'Ola', 'ola cabs': 'Ola', 'ola electric': 'Ola Electric',
    'google': 'Google', 'google play': 'Google Play', 'google cloud': 'Google Cloud',
    'apple': 'Apple', 'apple.com': 'Apple', 'itunes': 'Apple',
    'hotstar': 'Disney+ Hotstar', 'disney+': 'Disney+ Hotstar',
    'jio': 'Jio', 'reliance jio': 'Jio', 'jio fiber': 'Jio Fiber',
    'airtel': 'Airtel', 'bharti airtel': 'Airtel',
    'vi': 'Vi', 'vodafone': 'Vi', 'idea': 'Vi',
    'paytm': 'Paytm', 'phonepe': 'PhonePe', 'phone pe': 'PhonePe',
    'gpay': 'Google Pay', 'google pay': 'Google Pay',
    'myntra': 'Myntra', 'ajio': 'Ajio',
    'bigbasket': 'BigBasket', 'blinkit': 'Blinkit', 'zepto': 'Zepto',
    'cred': 'CRED', 'cred club': 'CRED',
    'youtube': 'YouTube Premium', 'yt premium': 'YouTube Premium',
    'chatgpt': 'OpenAI', 'openai': 'OpenAI',
    'icloud': 'Apple iCloud', 'apple icloud': 'Apple iCloud',
    'razorpay': 'Razorpay', 'payu': 'PayU', 'cashfree': 'Cashfree',
    'irctc': 'IRCTC', 'makemytrip': 'MakeMyTrip', 'goibibo': 'Goibibo',
    'lenskart': 'Lenskart', 'nykaa': 'Nykaa', 'meesho': 'Meesho',
    'dunzo': 'Dunzo', 'rapido': 'Rapido',
    'hdfc': 'HDFC Bank', 'sbi': 'SBI', 'icici': 'ICICI Bank',
    'axis': 'Axis Bank', 'kotak': 'Kotak Mahindra Bank',
    # Transit & NCMC
    'offline wallet': 'Metro / Transit Wallet',
    'offline wallet of prepaid': 'Metro / Transit Wallet',
    'offline wallet of prepaid card': 'Metro / Transit Wallet',
}


def normalize_merchant(raw: str) -> str:
    """Normalize merchant name using alias dictionary + text cleaning."""
    if not raw:
        return "Unknown"

    cleaned = raw.strip().lower()
    # Remove noise tokens
    noise = ['pvt', 'ltd', 'limited', 'private', 'inc', 'llp', 'llc', 'india', 'technologies']
    for n in noise:
        cleaned = re.sub(rf'\b{n}\b', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Check exact aliases
    if cleaned in MERCHANT_ALIASES:
        return MERCHANT_ALIASES[cleaned]

    # Check partial matches (only for aliases >= 4 chars to avoid false positives)
    for alias, canonical in MERCHANT_ALIASES.items():
        if len(alias) >= 4 and alias in cleaned:
            return canonical

    # Title case the cleaned name
    return raw.strip().title() if raw else "Unknown"





def extract_transaction_date(text: str) -> Optional[str]:
    """Extract transaction date from text."""
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            date_str = match.group(1)
            # Try parsing
            for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%d-%m-%y', '%d/%m/%y',
                        '%Y-%m-%d', '%d %b %Y', '%d %B %Y'):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue

    return None


def extract_transaction_fields(text: str, sender: str = "") -> Dict:
    """
    Extract all structured fields from SMS/notification text.
    
    Returns dict with: amount, direction, merchant, bank, payment_method,
    upi_ref, account_last4, transaction_date, balance_after, source
    """
    result = {
        "amount": 0.0,
        "direction": "debit",
        "merchant": "Unknown",
        "merchant_raw": None,
        "bank": None,
        "payment_method": None,
        "upi_ref": None,
        "account_last4": None,
        "transaction_date": None,
        "balance_after": None,
    }

    if not text:
        return result

    # Amount
    amount = extract_amount(text)
    if amount:
        result["amount"] = amount

    # Direction
    result["direction"] = classify_direction(text)

    # Merchant
    merchant = extract_merchant(text)
    if merchant:
        result["merchant"] = merchant
        result["merchant_raw"] = text

    # Bank
    result["bank"] = detect_bank(text, sender)

    # Payment method / rail
    result["payment_method"] = detect_payment_rail(text)

    # UPI reference
    upi_match = UPI_REF_PATTERN.search(text)
    if upi_match:
        result["upi_ref"] = upi_match.group(1)

    # Account last 4
    acc_match = ACCOUNT_PATTERN.search(text)
    if acc_match:
        result["account_last4"] = acc_match.group(1)

    # Transaction date
    result["transaction_date"] = extract_transaction_date(text)
    if not result["transaction_date"]:
        result["transaction_date"] = datetime.utcnow().isoformat()

    # Balance after
    result["balance_after"] = extract_balance(text)

    return result
