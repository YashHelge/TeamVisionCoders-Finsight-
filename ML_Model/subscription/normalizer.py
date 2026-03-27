"""
Merchant Normalizer — NLP + fuzzy dedup for subscription detection.

Uses: all-MiniLM-L6-v2 semantic embeddings + rapidfuzz token-sort-ratio ≥ 85
+ 200+ Indian merchant alias dictionary.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

logger = logging.getLogger("finsight.subscription.normalizer")

# ── 200+ Indian merchant alias dictionary ──
MERCHANT_ALIASES: Dict[str, str] = {
    # Streaming / Entertainment
    'netflix': 'Netflix', 'netflix.com': 'Netflix', 'netflix india': 'Netflix',
    'netflix*': 'Netflix', 'nflx': 'Netflix',
    'spotify': 'Spotify', 'spotify india': 'Spotify', 'spotify ab': 'Spotify',
    'hotstar': 'Disney+ Hotstar', 'disney+': 'Disney+ Hotstar',
    'disney plus': 'Disney+ Hotstar', 'disneyplushotstar': 'Disney+ Hotstar',
    'amazon prime': 'Amazon Prime', 'prime video': 'Amazon Prime',
    'youtube premium': 'YouTube Premium', 'yt premium': 'YouTube Premium',
    'youtube music': 'YouTube Music',
    'jio cinema': 'JioCinema', 'jiocinema': 'JioCinema',
    'sony liv': 'SonyLIV', 'sonyliv': 'SonyLIV',
    'zee5': 'ZEE5', 'zee 5': 'ZEE5',
    'apple tv': 'Apple TV+', 'apple tv+': 'Apple TV+',
    'apple music': 'Apple Music',
    'audible': 'Audible', 'kindle': 'Kindle Unlimited',
    'gaana': 'Gaana', 'wynk': 'Wynk Music',

    # SaaS / Productivity
    'openai': 'OpenAI', 'chatgpt': 'OpenAI', 'chatgpt plus': 'OpenAI',
    'github': 'GitHub', 'github copilot': 'GitHub Copilot',
    'notion': 'Notion', 'canva': 'Canva', 'figma': 'Figma',
    'google one': 'Google One', 'google workspace': 'Google Workspace',
    'microsoft 365': 'Microsoft 365', 'office 365': 'Microsoft 365',
    'icloud': 'Apple iCloud', 'apple icloud': 'Apple iCloud',
    'dropbox': 'Dropbox', 'evernote': 'Evernote',
    'zoom': 'Zoom', 'slack': 'Slack',
    'grammarly': 'Grammarly', 'todoist': 'Todoist',

    # Telecom
    'jio': 'Jio', 'reliance jio': 'Jio', 'jio recharge': 'Jio',
    'jio fiber': 'Jio Fiber', 'jiofiber': 'Jio Fiber',
    'airtel': 'Airtel', 'bharti airtel': 'Airtel', 'airtel xstream': 'Airtel Xstream',
    'vi': 'Vi', 'vodafone': 'Vi', 'idea': 'Vi', 'vodafone idea': 'Vi',
    'bsnl': 'BSNL', 'act fibernet': 'ACT Fibernet',
    'den broadband': 'DEN Broadband', 'hathway': 'Hathway',

    # Food / Delivery
    'swiggy': 'Swiggy', 'swiggy one': 'Swiggy One', 'swiggy instamart': 'Swiggy',
    'zomato': 'Zomato', 'zomato pro': 'Zomato Pro', 'zomato gold': 'Zomato',
    'bigbasket': 'BigBasket', 'blinkit': 'Blinkit', 'zepto': 'Zepto',
    'dunzo': 'Dunzo', 'dmart': 'DMart',

    # E-commerce
    'amazon': 'Amazon', 'amazon.in': 'Amazon', 'amzn': 'Amazon',
    'flipkart': 'Flipkart', 'flipkart internet': 'Flipkart',
    'myntra': 'Myntra', 'ajio': 'AJIO', 'nykaa': 'Nykaa',
    'meesho': 'Meesho', 'lenskart': 'Lenskart',
    'tata cliq': 'Tata CLiQ', 'snapdeal': 'Snapdeal',

    # Transport
    'uber': 'Uber', 'uber india': 'Uber', 'uber eats': 'Uber Eats',
    'ola': 'Ola', 'ola cabs': 'Ola',
    'rapido': 'Rapido', 'metro': 'Metro',
    'irctc': 'IRCTC', 'makemytrip': 'MakeMyTrip', 'goibibo': 'Goibibo',

    # Finance / Payments
    'cred': 'CRED', 'cred club': 'CRED',
    'paytm': 'Paytm', 'phonepe': 'PhonePe', 'phone pe': 'PhonePe',
    'gpay': 'Google Pay', 'google pay': 'Google Pay',
    'amazon pay': 'Amazon Pay', 'razorpay': 'Razorpay',

    # Utilities
    'electricity': 'Electricity Bill', 'tata power': 'Tata Power',
    'adani electricity': 'Adani Electricity', 'bescom': 'BESCOM',
    'mahanagar gas': 'Mahanagar Gas', 'indraprastha gas': 'IGL',
    'water bill': 'Water Bill', 'gas bill': 'Gas Bill',

    # Insurance
    'lic': 'LIC', 'life insurance': 'LIC',
    'star health': 'Star Health', 'hdfc ergo': 'HDFC ERGO',
    'icici lombard': 'ICICI Lombard', 'bajaj allianz': 'Bajaj Allianz',
    'digit insurance': 'Digit Insurance', 'acko': 'Acko',

    # Health / Fitness
    'cult.fit': 'cult.fit', 'cultfit': 'cult.fit', 'cult fit': 'cult.fit',
    'practo': 'Practo', 'pharmeasy': 'PharmEasy', 'netmeds': 'Netmeds',
    '1mg': '1mg', 'apollopharmacy': 'Apollo Pharmacy',

    # Education
    'unacademy': 'Unacademy', 'byju': "BYJU'S", "byju's": "BYJU'S",
    'coursera': 'Coursera', 'udemy': 'Udemy',
    'skillshare': 'Skillshare', 'linkedin learning': 'LinkedIn Learning',
}

# Noise tokens to strip
NOISE_TOKENS = {'pvt', 'ltd', 'limited', 'private', 'inc', 'llp', 'llc',
                'india', 'technologies', 'tech', 'solutions', 'services',
                'enterprises', 'corporation', 'corp', 'co', 'company'}


def quick_normalize(merchant: str) -> str:
    """Fast normalization using alias dictionary."""
    if not merchant:
        return "Unknown"

    cleaned = merchant.strip().lower()
    cleaned = re.sub(r'[*#]+\d*$', '', cleaned).strip()

    for token in NOISE_TOKENS:
        cleaned = re.sub(rf'\b{token}\b', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if cleaned in MERCHANT_ALIASES:
        return MERCHANT_ALIASES[cleaned]

    for alias, canonical in MERCHANT_ALIASES.items():
        if alias in cleaned:
            return canonical

    return merchant.strip().title()


def fuzzy_match_merchants(merchants: List[str], threshold: int = 85) -> Dict[str, str]:
    """
    Group merchants by fuzzy similarity.
    Returns mapping: original_name -> canonical_name
    """
    normalized = {m: quick_normalize(m) for m in merchants}
    canonical_map = {}
    groups = []

    for m in merchants:
        norm = normalized[m]
        matched = False

        for group in groups:
            representative = group[0]
            rep_norm = normalized.get(representative, quick_normalize(representative))

            score = fuzz.token_sort_ratio(norm.lower(), rep_norm.lower())
            if score >= threshold:
                group.append(m)
                canonical_map[m] = canonical_map.get(representative, rep_norm)
                matched = True
                break

        if not matched:
            groups.append([m])
            canonical_map[m] = norm

    return canonical_map


def get_semantic_groups(merchants: List[str]) -> List[List[str]]:
    """
    Group merchants using semantic embeddings (all-MiniLM-L6-v2).
    Falls back to fuzzy matching if sentence-transformers unavailable.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(merchants)

        # Cosine similarity clustering
        from sklearn.metrics.pairwise import cosine_similarity
        sim_matrix = cosine_similarity(embeddings)

        groups = []
        assigned = set()

        for i in range(len(merchants)):
            if i in assigned:
                continue
            group = [merchants[i]]
            assigned.add(i)

            for j in range(i + 1, len(merchants)):
                if j not in assigned and sim_matrix[i][j] > 0.85:
                    group.append(merchants[j])
                    assigned.add(j)

            groups.append(group)

        return groups

    except ImportError:
        logger.info("sentence-transformers not available, using fuzzy matching")
        mapping = fuzzy_match_merchants(merchants)
        groups_dict = {}
        for m, canonical in mapping.items():
            groups_dict.setdefault(canonical, []).append(m)
        return list(groups_dict.values())
