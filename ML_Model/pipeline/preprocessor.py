"""
Preprocessor — Text normalization and 48-feature engineered vector extraction.
"""

import re
import math
import hashlib
from typing import Dict, List, Tuple, Optional
from datetime import datetime


# ── Indian banking SMS patterns ──
AMOUNT_PATTERN = re.compile(
    r'(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{1,2})?)', re.IGNORECASE
)
AMOUNT_PATTERN_ALT = re.compile(
    r'(?:debited|credited|paid|received|sent|amount)\s*(?:of\s*)?(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
    re.IGNORECASE
)

BALANCE_PATTERN = re.compile(
    r'(?:bal|balance|avl\.?\s*bal|available\s*balance)[:\s]*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
    re.IGNORECASE
)

ACCOUNT_PATTERN = re.compile(r'(?:a/c|ac|account|acct)[:\s]*[*xX]*(\d{4})', re.IGNORECASE)

UPI_REF_PATTERN = re.compile(r'(?:UPI\s*(?:Ref|ref\.?|ID)?[:\s]*|ref[:\s]*)(\d{10,12})', re.IGNORECASE)

# Bank shortcodes (common Indian banks)
BANK_SENDERS = {
    'HDFCBK': 'HDFC Bank', 'SBIINB': 'SBI', 'ICICIB': 'ICICI Bank',
    'AXISBK': 'Axis Bank', 'KOTAKB': 'Kotak', 'PNBSMS': 'PNB',
    'BOIIND': 'BOI', 'CANBNK': 'Canara Bank', 'UNIONB': 'Union Bank',
    'IABORB': 'IOB', 'CENTBK': 'Central Bank', 'BOBITN': 'BOB',
    'YESBNK': 'Yes Bank', 'INDBNK': 'IndusInd', 'FEDBNK': 'Federal Bank',
    'IDFCFB': 'IDFC First', 'RBLBNK': 'RBL Bank', 'DCBBNK': 'DCB Bank',
    'SCBANK': 'Standard Chartered', 'CITIBK': 'Citibank',
    'HSBCBK': 'HSBC', 'DBS': 'DBS', 'PAYTMB': 'Paytm Payments Bank',
    'JUPBNK': 'Jupiter', 'FIBNK': 'Fi Money',
}

# Payment rail indicators
PAYMENT_RAILS = {
    'UPI': 'upi', 'NEFT': 'neft', 'IMPS': 'imps', 'RTGS': 'rtgs',
    'NACH': 'nach', 'ECS': 'ecs', 'ATM': 'atm',
}

# OTP indicators
OTP_PATTERNS = [
    r'\bOTP\b', r'\bone[- ]?time[- ]?password\b', r'\bverification\s*code\b',
    r'\bCVV\b', r'\bPIN\b', r'\bsecure\s*code\b',
    r'\b\d{4,8}\b.*(?:otp|code|verify|valid\s*for)',
]

# Promotional patterns
PROMO_PATTERNS = [
    r'\bcashback\b', r'\breward\b', r'\boffer\b', r'\bdiscount\b',
    r'\bcoupon\b', r'\bwin\b', r'\bfree\b', r'\bexclusive\b',
    r'\blimited\s*time\b', r'\bhurry\b', r'\bsubscribe\b',
    r'\bunsubscribe\b', r'\bopt[- ]?out\b', r'\bT&C\b',
]

# Phishing/spam patterns
PHISHING_PATTERNS = [
    r'\blottery\b', r'\bcongratulations\b.*\bwon\b', r'\bclaim\s*your\b',
    r'\bKYC\s*(expir|updat|verif)\b', r'\bblock\w*\s*(?:card|account)\b',
    r'\bsuspicious\s*activity\b', r'\bclick\s*(?:here|below|link)\b',
    r'(?:bit\.ly|tinyurl|goo\.gl|short\.url)',
]


def normalize_text(text: str) -> str:
    """Normalize SMS text for processing."""
    if not text:
        return ""
    # Lowercase
    text = text.lower().strip()
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    # Expand common abbreviations
    abbrevs = {
        'a/c': 'account', 'ac': 'account', 'acct': 'account',
        'txn': 'transaction', 'trx': 'transaction',
        'amt': 'amount', 'bal': 'balance', 'avl': 'available',
        'cr': 'credit', 'dr': 'debit', 'debited': 'debited',
        'credited': 'credited', 'ref': 'reference',
        'rs': 'rupees', 'inr': 'rupees',
    }
    for abbr, full in abbrevs.items():
        text = re.sub(rf'\b{abbr}\b', full, text)
    return text


def extract_amount(text: str) -> Optional[float]:
    """Extract the primary monetary amount from text."""
    match = AMOUNT_PATTERN.search(text)
    if not match:
        match = AMOUNT_PATTERN_ALT.search(text)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            return float(amount_str)
        except ValueError:
            pass
    return None


def extract_balance(text: str) -> Optional[float]:
    """Extract available balance from text."""
    match = BALANCE_PATTERN.search(text)
    if match:
        bal_str = match.group(1).replace(',', '')
        try:
            return float(bal_str)
        except ValueError:
            pass
    return None


def classify_direction(text: str) -> str:
    """Classify transaction as credit or debit."""
    text_lower = text.lower()
    credit_keywords = ['credited', 'received', 'credit', 'deposited', 'refund', 'reversed', 'cashback']
    debit_keywords = ['debited', 'paid', 'debit', 'withdrawn', 'sent', 'transferred', 'purchased', 'spent']

    credit_score = sum(1 for k in credit_keywords if k in text_lower)
    debit_score = sum(1 for k in debit_keywords if k in text_lower)

    return 'credit' if credit_score > debit_score else 'debit'


def detect_payment_rail(text: str) -> Optional[str]:
    """Detect payment rail (UPI, NEFT, IMPS, etc.)."""
    text_upper = text.upper()
    for rail, label in PAYMENT_RAILS.items():
        if rail in text_upper:
            return label
    return None


def detect_bank(text: str, sender: str = "") -> Optional[str]:
    """Detect bank from sender shortcode or text."""
    sender_upper = sender.upper()
    for code, bank in BANK_SENDERS.items():
        if code in sender_upper:
            return bank

    # Try matching from text
    text_lower = text.lower()
    bank_names = [
        ('hdfc', 'HDFC Bank'), ('sbi', 'SBI'), ('icici', 'ICICI Bank'),
        ('axis', 'Axis Bank'), ('kotak', 'Kotak'), ('pnb', 'PNB'),
        ('bob', 'BOB'), ('canara', 'Canara Bank'), ('yes bank', 'Yes Bank'),
        ('indusind', 'IndusInd'), ('federal', 'Federal Bank'),
        ('idfc', 'IDFC First'), ('rbl', 'RBL Bank'), ('paytm', 'Paytm'),
        ('jupiter', 'Jupiter'), ('fi money', 'Fi Money'),
    ]
    for keyword, bank in bank_names:
        if keyword in text_lower:
            return bank
    return None


def engineer_features(text: str, sender: str = "") -> List[float]:
    """
    Extract 48-dimensional feature vector from SMS/notification text.
    
    Features grouped into:
    - Text metrics (12): length, word count, digit ratio, etc.
    - Amount features (6): amount value, log amount, has amount, etc.
    - Direction features (4): credit/debit indicators
    - Payment rail (8): UPI, NEFT, IMPS, etc. one-hot
    - Bank signals (6): sender type, known bank, etc.
    - Fraud signals (4): phishing indicators
    - Source signals (4): SMS vs notification indicators
    - Temporal (4): hour, day of week, etc.
    """
    features = []
    text_lower = text.lower()
    normalized = normalize_text(text)

    # ── Text metrics (12) ──
    features.append(len(text))  # 1. text length
    features.append(len(text.split()))  # 2. word count
    features.append(sum(c.isdigit() for c in text) / max(len(text), 1))  # 3. digit ratio
    features.append(sum(c.isupper() for c in text) / max(len(text), 1))  # 4. uppercase ratio
    features.append(text.count('.'))  # 5. period count
    features.append(text.count(','))  # 6. comma count
    features.append(1.0 if '₹' in text or 'Rs' in text or 'INR' in text else 0.0)  # 7. has currency
    features.append(1.0 if re.search(r'http|www|\.com|\.in', text_lower) else 0.0)  # 8. has URL
    features.append(1.0 if '@' in text else 0.0)  # 9. has email/UPI
    features.append(text.count('*'))  # 10. asterisk count (masking)
    features.append(1.0 if re.search(r'\d{4}[- ]?\d{4}[- ]?\d{4}', text) else 0.0)  # 11. has card number
    features.append(len(re.findall(r'\d+', text)))  # 12. number token count

    # ── Amount features (6) ──
    amount = extract_amount(text)
    features.append(amount if amount else 0.0)  # 13. raw amount
    features.append(math.log1p(amount) if amount else 0.0)  # 14. log amount
    features.append(1.0 if amount else 0.0)  # 15. has amount
    features.append(1.0 if amount and amount > 10000 else 0.0)  # 16. large transaction
    features.append(1.0 if amount and amount < 10 else 0.0)  # 17. micro transaction
    balance = extract_balance(text)
    features.append(math.log1p(balance) if balance else 0.0)  # 18. log balance

    # ── Direction features (4) ──
    direction = classify_direction(text)
    features.append(1.0 if direction == 'credit' else 0.0)  # 19. is credit
    features.append(1.0 if direction == 'debit' else 0.0)  # 20. is debit
    features.append(1.0 if 'refund' in text_lower else 0.0)  # 21. is refund
    features.append(1.0 if 'reversal' in text_lower or 'reversed' in text_lower else 0.0)  # 22. is reversal

    # ── Payment rail one-hot (8) ──
    rail = detect_payment_rail(text)
    rails = ['upi', 'neft', 'imps', 'rtgs', 'nach', 'ecs', 'atm', None]
    for r in rails:
        features.append(1.0 if rail == r else 0.0)  # 23-30

    # ── Bank signals (6) ──
    bank = detect_bank(text, sender)
    features.append(1.0 if bank else 0.0)  # 31. known bank
    features.append(1.0 if len(sender) <= 8 and sender.isalpha() else 0.0)  # 32. shortcode sender
    features.append(1.0 if re.search(r'\d{10}', sender) else 0.0)  # 33. phone number sender
    features.append(1.0 if re.search(ACCOUNT_PATTERN, text) else 0.0)  # 34. has account number
    features.append(1.0 if re.search(UPI_REF_PATTERN, text) else 0.0)  # 35. has UPI ref
    features.append(1.0 if 'transaction' in text_lower or 'txn' in text_lower else 0.0)  # 36. mentions transaction

    # ── Fraud signals (4) ──
    features.append(sum(1 for p in PHISHING_PATTERNS if re.search(p, text, re.IGNORECASE)))  # 37. phishing score
    features.append(sum(1 for p in OTP_PATTERNS if re.search(p, text, re.IGNORECASE)))  # 38. OTP score
    features.append(sum(1 for p in PROMO_PATTERNS if re.search(p, text, re.IGNORECASE)))  # 39. promo score
    features.append(1.0 if '!' in text and text.count('!') > 2 else 0.0)  # 40. exclamation spam

    # ── Source signals (4) ──
    features.append(0.0)  # 41. is_notification (set externally)
    features.append(1.0)  # 42. is_sms (default, set externally)
    features.append(0.0)  # 43. is_merged
    features.append(0.0)  # 44. is_dataset

    # ── Temporal (4) ──
    now = datetime.now()
    features.append(now.hour / 24.0)  # 45. normalized hour
    features.append(now.weekday() / 7.0)  # 46. normalized day of week
    features.append(1.0 if now.hour < 6 or now.hour > 22 else 0.0)  # 47. unusual hour
    features.append(1.0 if now.weekday() >= 5 else 0.0)  # 48. weekend

    return features


def compute_fingerprint(
    amount: float,
    merchant: str,
    timestamp_ms: int,
    direction: str,
) -> str:
    """
    Compute SHA-256 transaction fingerprint.
    
    fingerprint = SHA-256("{norm_amount}|{canon_merchant}|{time_bucket}|{direction}")
    """
    norm_amount = f"{amount:.2f}"
    canon_merchant = merchant.lower().strip()
    time_bucket = timestamp_ms // 900_000  # 15-minute window
    
    fp_string = f"{norm_amount}|{canon_merchant}|{time_bucket}|{direction}"
    return hashlib.sha256(fp_string.encode()).hexdigest()
