import os
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

async def batch_extract_llm(sms_list: List[str]) -> List[Dict[str, str]]:
    """
    Extracts category and clean merchant from a batch of up to 50 SMS.
    Uses a single LLM call to save API rate limits!
    
    Returns a list of dicts: [{"merchant": "Netflix", "category": "entertainment"}, ...]
    """
    if not sms_list:
        return []

    instructions = (
        "You are an expert financial SMS parser for Indian bank transactions.\n"
        "Your job is to read an array of raw SMS messages and return a JSON object containing an array 'results'.\n"
        "For each SMS, you must return:\n"
        "1. 'merchant': The clean, human-readable name of the payee/sender (e.g., 'Swiggy', 'Netflix', 'Subhash Hariram', 'SBI', 'Metro Transit').\n"
        "2. 'category': Exactly ONE of the following precise categories based on the merchant and context:\n"
        "   income, rent_emi, utilities, food_dining, shopping, transport, healthcare, entertainment, investment, telecom, finance, financial_transaction, uncategorized.\n"
        "3. 'amount': The monetary amount of the transaction as a number (e.g., 150.0). If you cannot find any amount, return null.\n"
        "4. 'direction': Either 'credit' or 'debit'. If money left the user's account, it is 'debit'. If money entered, it is 'credit'.\n"
        "\n"
        "IMPORTANT RULES:\n"
        "- If it's a person paying the user via UPI, merchant = person's name, category = 'income'.\n"
        "- If the user pays a person via UPI, merchant = person's name, category = 'uncategorized' (unless context implies otherwise).\n"
        "- Strip out 'Rs.', dates, 'UPI', and bank names from the merchant string. Make it title case.\n"
        "- If the SMS is not a transaction (e.g., OTP, alert), return merchant='Unknown', category='uncategorized', amount=null, direction='debit'.\n"
        "- Output strict JSON format: {\"results\": [{\"merchant\": \"X\", \"category\": \"Y\", \"amount\": 150.0, \"direction\": \"debit\"}, ...]}\n\n"
    )

    # Format the input as a numbered list
    user_prompt = instructions + "Parse the following SMS messages:\n\n"
    for i, sms in enumerate(sms_list):
        user_prompt += f"[{i}] {sms}\n"

    try:
        from groq_client import complete_json
        
        data = await complete_json(user_prompt)
        if not data:
            return _fallback_results(len(sms_list))

        results = data.get("results", [])
        
        # Validate count
        if len(results) != len(sms_list):
            logger.warning(f"LLM returned {len(results)} results, expected {len(sms_list)}")
            # Pad with fallbacks if missing
            while len(results) < len(sms_list):
                results.append({"merchant": "Unknown", "category": "uncategorized", "amount": None, "direction": "debit"})
            results = results[:len(sms_list)]
            
        return results

    except Exception as e:
        logger.error(f"Batch LLM Extraction failed: {e}")
        return _fallback_results(len(sms_list))


def _fallback_results(count: int) -> List[Dict[str, str]]:
    return [{"merchant": "Unknown", "category": "uncategorized", "amount": None, "direction": "debit"} for _ in range(count)]
