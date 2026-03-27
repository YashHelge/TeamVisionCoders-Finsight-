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

# ── Merchant extraction patterns ──
MERCHANT_PATTERNS = [
    # "to MERCHANT" or "at MERCHANT" or "from MERCHANT"
    re.compile(r'(?:to|at|from|paid\s+to|sent\s+to|received\s+from)\s+([A-Za-z0-9][A-Za-z0-9\s&.\'-]{1,40}?)(?:\s+(?:on|via|ref|upi|a/c|ac|\d))', re.IGNORECASE),
    # "VPA merchant@bank"
    re.compile(r'VPA\s+([a-zA-Z0-9._-]+)@', re.IGNORECASE),
    # "trf to MERCHANT" / "trf from MERCHANT"
    re.compile(r'(?:trf|transfer)\s+(?:to|from)\s+([A-Za-z0-9][A-Za-z0-9\s&.\'-]{1,40}?)(?:\s|$)', re.IGNORECASE),
    # Between hyphens in bank SMS: "Info: MERCHANT-"
    re.compile(r'(?:Info|info|INFO)[:\s]*([A-Za-z0-9][A-Za-z0-9\s&.\'-]{2,30}?)(?:\s*-\s*|\s+(?:UPI|NEFT|IMPS))', re.IGNORECASE),
]

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

    # Check aliases
    if cleaned in MERCHANT_ALIASES:
        return MERCHANT_ALIASES[cleaned]

    # Check partial matches
    for alias, canonical in MERCHANT_ALIASES.items():
        if alias in cleaned:
            return canonical

    # Title case the cleaned name
    return raw.strip().title() if raw else "Unknown"


def extract_merchant(text: str) -> Optional[str]:
    """Extract merchant name from SMS/notification text."""
    for pattern in MERCHANT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            if len(raw) > 2:  # Skip very short matches
                return normalize_merchant(raw)

    return None


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
