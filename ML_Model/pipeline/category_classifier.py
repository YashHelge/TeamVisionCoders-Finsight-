"""
Spending Category Classifier — Assigns meaningful spending categories
to financial transactions based on merchant name and SMS content.

Categories: food_dining, shopping, transport, entertainment, utilities,
health, education, travel, groceries, rent_emi, investment, insurance,
salary, income, subscriptions, finance, telecom, upi_transfer, uncategorized
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("finsight.pipeline.category_classifier")

# ── Merchant → Category mapping (known merchants) ──
MERCHANT_CATEGORY_MAP = {
    # Food & Dining
    'swiggy': 'food_dining', 'zomato': 'food_dining', 'uber eats': 'food_dining',
    'dominos': 'food_dining', 'pizza hut': 'food_dining', 'mcdonald': 'food_dining',
    'kfc': 'food_dining', 'burger king': 'food_dining', 'starbucks': 'food_dining',
    'cafe coffee day': 'food_dining', 'chaayos': 'food_dining', 'haldiram': 'food_dining',
    'restaurant': 'food_dining', 'food': 'food_dining', 'dine': 'food_dining',
    'eat': 'food_dining', 'biryani': 'food_dining', 'cafe': 'food_dining',
    'bakery': 'food_dining', 'dhaba': 'food_dining', 'hotel': 'food_dining',
    # Groceries
    'bigbasket': 'groceries', 'blinkit': 'groceries', 'zepto': 'groceries',
    'dmart': 'groceries', 'reliance fresh': 'groceries', 'more supermarket': 'groceries',
    'jiomart': 'groceries', 'nature basket': 'groceries', 'instamart': 'groceries',
    'grocery': 'groceries', 'supermarket': 'groceries', 'kirana': 'groceries',
    'dunzo': 'groceries', 'swiggy instamart': 'groceries',
    # Shopping
    'amazon': 'shopping', 'flipkart': 'shopping', 'myntra': 'shopping',
    'ajio': 'shopping', 'meesho': 'shopping', 'snapdeal': 'shopping',
    'nykaa': 'shopping', 'lenskart': 'shopping', 'tata cliq': 'shopping',
    'croma': 'shopping', 'reliance digital': 'shopping',
    'shoppers stop': 'shopping', 'lifestyle': 'shopping',
    # Transport
    'uber': 'transport', 'ola': 'transport', 'rapido': 'transport',
    'metro': 'transport', 'irctc': 'transport', 'petrol': 'transport',
    'fuel': 'transport', 'parking': 'transport', 'toll': 'transport',
    'fastag': 'transport', 'indian oil': 'transport', 'hp petrol': 'transport',
    'bharat petroleum': 'transport', 'rapido bike': 'transport',
    # Travel
    'makemytrip': 'travel', 'goibibo': 'travel', 'yatra': 'travel',
    'cleartrip': 'travel', 'easemytrip': 'travel', 'ixigo': 'travel',
    'oyo': 'travel', 'airbnb': 'travel', 'indigo': 'travel',
    'air india': 'travel', 'spicejet': 'travel', 'vistara': 'travel',
    'redbus': 'travel', 'abhibus': 'travel',
    # Entertainment
    'netflix': 'entertainment', 'hotstar': 'entertainment', 'disney': 'entertainment',
    'prime video': 'entertainment', 'sony liv': 'entertainment', 'zee5': 'entertainment',
    'youtube premium': 'entertainment', 'spotify': 'entertainment',
    'gaana': 'entertainment', 'jiocinema': 'entertainment',
    'pvr': 'entertainment', 'inox': 'entertainment', 'bookmyshow': 'entertainment',
    'cinema': 'entertainment', 'movie': 'entertainment', 'gaming': 'entertainment',
    # Subscriptions
    'chatgpt': 'subscriptions', 'openai': 'subscriptions', 'apple icloud': 'subscriptions',
    'google one': 'subscriptions', 'linkedin premium': 'subscriptions',
    'microsoft 365': 'subscriptions', 'dropbox': 'subscriptions',
    'icloud': 'subscriptions',
    # Utilities
    'electricity': 'utilities', 'water bill': 'utilities', 'gas bill': 'utilities',
    'bescom': 'utilities', 'msedcl': 'utilities', 'tata power': 'utilities',
    'adani gas': 'utilities', 'mahanagar gas': 'utilities',
    'indra pani': 'utilities', 'piped gas': 'utilities',
    # Telecom
    'airtel': 'telecom', 'jio': 'telecom', 'vi': 'telecom', 'vodafone': 'telecom',
    'idea': 'telecom', 'bsnl': 'telecom', 'mtnl': 'telecom',
    'jio fiber': 'telecom', 'airtel fiber': 'telecom',
    'act fibernet': 'telecom', 'hathway': 'telecom',
    # Health
    'pharmacy': 'health', 'pharmeasy': 'health', '1mg': 'health',
    'netmeds': 'health', 'apollo': 'health', 'medplus': 'health',
    'hospital': 'health', 'clinic': 'health', 'diagnostic': 'health',
    'pathology': 'health', 'doctor': 'health', 'medical': 'health',
    # Education
    'udemy': 'education', 'coursera': 'education', 'unacademy': 'education',
    'byju': 'education', 'school': 'education', 'college': 'education',
    'university': 'education', 'tuition': 'education', 'exam': 'education',
    # Insurance
    'lic': 'insurance', 'star health': 'insurance', 'max life': 'insurance',
    'hdfc ergo': 'insurance', 'icici lombard': 'insurance',
    'bajaj allianz': 'insurance', 'tata aia': 'insurance',
    'insurance': 'insurance', 'premium': 'insurance', 'policy': 'insurance',
    # Investment
    'zerodha': 'investment', 'groww': 'investment', 'upstox': 'investment',
    'angel one': 'investment', 'mutual fund': 'investment', 'sip': 'investment',
    'nps': 'investment', 'ppf': 'investment', 'fixed deposit': 'investment',
    # Finance (bank charges, EMI, etc.)
    'cred': 'finance', 'razorpay': 'finance', 'payu': 'finance',
    'cashfree': 'finance', 'loan': 'finance', 'emi': 'finance',
    # Rent & EMI
    'rent': 'rent_emi', 'landlord': 'rent_emi', 'society': 'rent_emi',
    'maintenance': 'rent_emi', 'housing': 'rent_emi',
}

# ── SMS content → Category patterns ──
CONTENT_CATEGORY_PATTERNS = [
    # Salary / Income
    (re.compile(r'\b(?:salary|stipend|wages?|payroll)\b', re.IGNORECASE), 'salary', 0.95),
    (re.compile(r'\b(?:pension|dividend|interest\s*(?:credit|received))\b', re.IGNORECASE), 'income', 0.90),
    (re.compile(r'\b(?:refund|cashback|reversal)\b', re.IGNORECASE), 'income', 0.85),
    # Rent / EMI
    (re.compile(r'\b(?:EMI|emi\s*payment|loan\s*repayment|instalment)\b', re.IGNORECASE), 'rent_emi', 0.90),
    (re.compile(r'\b(?:rent|house\s*rent|monthly\s*rent|maintenance)\b', re.IGNORECASE), 'rent_emi', 0.85),
    # Investment
    (re.compile(r'\b(?:SIP|mutual\s*fund|MF\s*purchase|zerodha|groww|upstox)\b', re.IGNORECASE), 'investment', 0.90),
    (re.compile(r'\b(?:FD|fixed\s*deposit|RD|recurring\s*deposit|NPS|PPF)\b', re.IGNORECASE), 'investment', 0.85),
    # Transport
    (re.compile(r'\b(?:uber|ola|rapido|petrol|diesel|fuel|toll|fastag|offline\s*wallet.*?prepaid\s*card)\b', re.IGNORECASE), 'transport', 0.90),
    (re.compile(r'\b(?:irctc|railway|train\s*ticket|metro|bus\s*ticket)\b', re.IGNORECASE), 'transport', 0.85),
    # Food
    (re.compile(r'\b(?:swiggy|zomato|dominos|pizza|restaurant|food\s*order)\b', re.IGNORECASE), 'food_dining', 0.90),
    # Groceries
    (re.compile(r'\b(?:bigbasket|blinkit|zepto|instamart|grocery|supermarket)\b', re.IGNORECASE), 'groceries', 0.90),
    # Entertainment
    (re.compile(r'\b(?:netflix|hotstar|prime\s*video|spotify|bookmyshow)\b', re.IGNORECASE), 'entertainment', 0.90),
    # Utilities
    (re.compile(r'\b(?:electricity|water\s*bill|gas\s*bill|bescom|msedcl)\b', re.IGNORECASE), 'utilities', 0.90),
    # Telecom
    (re.compile(r'\b(?:airtel|jio|vi\s|vodafone|bsnl|recharge)\b', re.IGNORECASE), 'telecom', 0.85),
    # Insurance
    (re.compile(r'\b(?:insurance|LIC|premium\s*(?:paid|due|deducted))\b', re.IGNORECASE), 'insurance', 0.85),
    # Shopping
    (re.compile(r'\b(?:amazon|flipkart|myntra|ajio|meesho|nykaa)\b', re.IGNORECASE), 'shopping', 0.90),
    (re.compile(r'\b(?:POS|pos\s*purchase|card\s*swipe)\b', re.IGNORECASE), 'shopping', 0.75),
    # Health
    (re.compile(r'\b(?:hospital|pharmacy|medical|doctor|diagnostic|apollo)\b', re.IGNORECASE), 'health', 0.85),
    # Education
    (re.compile(r'\b(?:school|college|university|tuition|exam|course\s*fee)\b', re.IGNORECASE), 'education', 0.85),
]


def classify_spending_category(text: str, merchant: str = "", direction: str = "debit") -> Tuple[str, float]:
    """
    Classify a confirmed financial transaction into a spending category.

    This runs AFTER the labeler confirms the SMS is a 'financial_transaction'.
    Returns: (category, confidence)
    """
    if not text:
        return ('uncategorized', 0.50)

    best_category = 'uncategorized'
    best_confidence = 0.0

    # ── Step 1: Check merchant name against known merchants ──
    if merchant:
        merchant_lower = merchant.lower().strip()
        for keyword, cat in MERCHANT_CATEGORY_MAP.items():
            if keyword in merchant_lower:
                return (cat, 0.92)

    # ── Step 2: Check SMS content against category patterns ──
    for pattern, cat, conf in CONTENT_CATEGORY_PATTERNS:
        if pattern.search(text):
            if conf > best_confidence:
                best_category = cat
                best_confidence = conf

    # ── Step 3: Direction-based inference for UPI P2P transfers ──
    if best_confidence < 0.70:
        text_lower = text.lower()

        # Credits from people (UPI P2P) → income
        if direction == 'credit':
            if re.search(r'(?:from|received\s+from)\s+[a-z]+\s+[a-z]+', text_lower):
                return ('income', 0.80)
            if re.search(r'(?:NEFT|IMPS|UPI)\s*(?:CR|credit)', text_lower):
                return ('income', 0.78)

        # Card transactions are usually shopping
        if re.search(r'(?:credit\s*card|debit\s*card|card\s*ending)', text_lower):
            if best_confidence < 0.75:
                best_category = 'shopping'
                best_confidence = 0.75

        # ATM withdrawal → finance
        if re.search(r'\b(?:ATM|cash\s*withdrawal)\b', text_lower):
            return ('finance', 0.85)

        # UPI transfers between individuals
        if re.search(r'(?:from|to)\s+[a-z]+\s+[a-z]+\s+(?:thru|via|through)', text_lower):
            if direction == 'credit':
                return ('income', 0.80)
            else:
                return ('finance', 0.75)

    if best_confidence < 0.50:
        return ('uncategorized', 0.50)

    return (best_category, best_confidence)
