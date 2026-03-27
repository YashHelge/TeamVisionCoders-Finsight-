"""
SMS Ingest API — Accepts raw SMS bodies directly from the mobile app.
Parses financial SMS, classifies them, and stores ONLY real transactions.

Key improvements:
- Only inserts SMS classified as 'financial_transaction'
- Validates amount > 0 (no zero-amount junk)
- Smart non-transaction detection (alerts, reminders, legal notices)
- Proper direction detection with exclusion patterns
"""

import hashlib
import logging
import re
import time
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.sms_ingest")


class SmsMessage(BaseModel):
    sender: str
    body: str
    timestamp: int  # epoch milliseconds
    date: str  # ISO 8601


class SmsIngestRequest(BaseModel):
    messages: List[SmsMessage]


class SmsIngestResponse(BaseModel):
    total_received: int
    total_processed: int
    total_classified: int
    total_skipped: int
    categories: dict
    processing_time_ms: int


# ── Non-transaction patterns (SMS mentions money but isn't a real transaction) ──
NON_TRANSACTION_PATTERNS = [
    # Bill reminders / outstanding alerts
    re.compile(r'(?:bill|amount|total|min|outstanding|amt)\s*(?:due|payable|is\s*due)', re.IGNORECASE),
    re.compile(r'(?:due\s*on\s*your|is\s+due\s+on)', re.IGNORECASE),
    re.compile(r'please\s*(?:pay|clear|settle|recharge)', re.IGNORECASE),
    re.compile(r'further\s*delay', re.IGNORECASE),
    re.compile(r'despite.*reminder', re.IGNORECASE),
    re.compile(r'several\s*reminders?', re.IGNORECASE),
    # Legal / collection threats
    re.compile(r'legal\s*(?:action|notice|proceedings?)', re.IGNORECASE),
    re.compile(r'(?:overdue|defaulted|past\s*due)', re.IGNORECASE),
    # Statement / summary notifications
    re.compile(r'statement\s*(?:generated|ready|available|for)', re.IGNORECASE),
    # Mandate / auto-debit status
    re.compile(r'mandate\s*(?:revoked|failed|rejected|created|registered)', re.IGNORECASE),
    re.compile(r'(?:autopay|auto-pay|mandate).*(?:scheduled|requested|setup)', re.IGNORECASE),
    re.compile(r'is\s*scheduled\s*on', re.IGNORECASE),
    # Failed / declined transactions
    re.compile(r'(?:txn|transaction|payment)\s*(?:of\s*(?:rs|inr|₹)[\d.,\s]*)?(?:has\s*)?(?:declined|failed|rejected)', re.IGNORECASE),
    re.compile(r'(?:declined|failed)\s*(?:due\s*to|for|at)\s*(?:insufficient|wrong|merchant)', re.IGNORECASE),
    # Data consumption alerts
    re.compile(r'data\s*is\s*consumed', re.IGNORECASE),
    re.compile(r'(?:50%|90%|100%)\s*(?:data|quota)', re.IGNORECASE),
    # KYC / verification requests (not transactions)
    re.compile(r'CKYCR|KYC\s*(?:document|update|verification|expir)', re.IGNORECASE),
    # Service alerts (Airtel, Jio recharge reminders)
    re.compile(r'(?:service|incoming)\s*(?:will\s*)?(?:stop|discontinue|expire)', re.IGNORECASE),
    re.compile(r'recharge\s*(?:NOW|today|immediately|urgently)', re.IGNORECASE),
    # OTP / verification
    re.compile(r'\bOTP\b', re.IGNORECASE),
    re.compile(r'one[- ]?time[- ]?password', re.IGNORECASE),
    re.compile(r'verification\s*code', re.IGNORECASE),
    # Promotional / marketing
    re.compile(r'(?:congratulations|congrats).*unlock', re.IGNORECASE),
    re.compile(r'(?:free|complimentary)\s*(?:trial|premium|subscription)', re.IGNORECASE),
    re.compile(r'(?:offer|discount|coupon|cashback)\s*(?:of|worth|upto|on)', re.IGNORECASE),
    # RBI / government advisory
    re.compile(r'(?:sachet|rbi\.org|epfindia|incometax)', re.IGNORECASE),
    re.compile(r'(?:तक्रार|योजन|अधिकार|सरकार)', re.IGNORECASE),  # Hindi/Marathi advisory
    # Fund / securities balance reports (not actual transactions)
    re.compile(r'reported.*(?:fund|securities)\s*bal', re.IGNORECASE),
    re.compile(r'(?:fund|securities)\s*bal.*reported', re.IGNORECASE),
    # Generic non-transactional
    re.compile(r'miss\s*call\s*\d+', re.IGNORECASE),
    re.compile(r'click\s*(?:here|below|on)', re.IGNORECASE),
]

# ── Transaction confirmation patterns (SMS IS a real transaction) ──
REAL_TRANSACTION_PATTERNS = [
    re.compile(r'(?:debited|credited)\s*(?:with\s*)?(?:Rs\.?|INR|₹)\s*[\d,]+', re.IGNORECASE),
    re.compile(r'(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{1,2})?\s*(?:debited|credited|paid|received|deposited)', re.IGNORECASE),
    re.compile(r'(?:sent|received|paid|transferred)\s*(?:Rs\.?|INR|₹)\s*[\d,]+', re.IGNORECASE),
    re.compile(r'(?:NEFT|IMPS|RTGS|UPI)\s*(?:of|for)?\s*(?:Rs\.?|INR|₹)\s*[\d,]+', re.IGNORECASE),
    re.compile(r'(?:purchase|POS|ATM|withdrawal)\s*(?:of|for)?\s*(?:Rs\.?|INR|₹)', re.IGNORECASE),
    re.compile(r'(?:credited|debited)\s*(?:to|from|in)\s*(?:your\s*)?(?:a/?c|account|card)', re.IGNORECASE),
    re.compile(r'(?:Payment\s*of)\s*(?:Rs\.?|INR|₹)\s*[\d,]+\s*(?:credited|received)', re.IGNORECASE),
    re.compile(r'(?:avl|available)\s*(?:bal|balance)', re.IGNORECASE),  # Balance mentioned = real txn
    re.compile(r'EMI\s*(?:of\s*)?(?:Rs\.?|INR|₹)\s*[\d,]+\s*(?:debited|deducted|paid)', re.IGNORECASE),
]


def _is_real_transaction(body: str) -> bool:
    """
    Smart validation: determine if an SMS is a REAL monetary transaction.
    Returns True only if the SMS describes an actual debit/credit event.
    """
    # Step 1: Check for explicit non-transaction patterns (high priority)
    non_txn_hits = sum(1 for pat in NON_TRANSACTION_PATTERNS if pat.search(body))
    if non_txn_hits >= 2:
        return False

    # Step 2: Check for real transaction confirmation patterns
    txn_hits = sum(1 for pat in REAL_TRANSACTION_PATTERNS if pat.search(body))
    if txn_hits >= 1:
        # Even if it matched a txn pattern, override if it's clearly an alert/reminder
        for pat in NON_TRANSACTION_PATTERNS[:8]:  # Only the first 8 (bill/legal/statement)
            if pat.search(body):
                return False
        return True

    # Step 3: If no clear transaction pattern matched, it's NOT a transaction
    return False


def _detect_direction(body: str) -> str:
    """Detect transaction direction with smarter keyword matching."""
    lower = body.lower()
    credit_kw = ['credited', 'received', 'deposited', 'refund', 'cashback', 'reversed']
    debit_kw = ['debited', 'withdrawn', 'sent', 'paid', 'purchase', 'spent', 'charged', 'deducted']

    # Find first occurrence
    first_credit = len(lower)
    first_debit = len(lower)

    for kw in credit_kw:
        pos = lower.find(kw)
        if pos != -1 and pos < first_credit:
            first_credit = pos
    for kw in debit_kw:
        pos = lower.find(kw)
        if pos != -1 and pos < first_debit:
            first_debit = pos

    if first_credit < first_debit:
        return "credit"
    elif first_debit < first_credit:
        return "debit"
    return "debit"


@router.post("/sms/ingest", response_model=SmsIngestResponse)
async def ingest_sms(
    request: Request,
    body: SmsIngestRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Ingest raw SMS messages from the mobile device.
    Runs full pipeline: classification → validation → extraction → storage.
    Only REAL transactions are stored (alerts, OTPs, promos are skipped).
    """
    start = time.time()

    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    processed = 0
    classified = 0
    skipped = 0
    categories = {}

    try:
        # === Phase 1: Rule-based Filtering & Extraction ===
        valid_txns = []
        for sms in body.messages:
            # === Step 1: Classify the SMS ===
            category = "uncategorized"
            confidence = 0.0
            try:
                from pipeline.labeler import rule_based_label
                category, confidence = rule_based_label(sms.body, sms.sender)
                if confidence < 0.80:
                    from pipeline.classifier import classify_text
                    category, confidence = await classify_text(sms.body)
            except Exception:
                pass

            classified += 1
            categories[category] = categories.get(category, 0) + 1

            # === Step 2: SKIP non-transaction SMS ===
            if category != 'financial_transaction':
                skipped += 1
                continue

            # === Step 3: Smart validation — is this REALLY a transaction? ===
            if not _is_real_transaction(sms.body):
                logger.debug("Skipped non-transaction SMS: %.80s...", sms.body)
                skipped += 1
                continue

            # === Step 4: Extract financial fields ===
            from pipeline.extractor import extract_merchant
            from pipeline.preprocessor import (
                extract_amount, detect_payment_rail, detect_bank,
            )

            amount = extract_amount(sms.body)

            # Skip zero-amount or no-amount SMS
            if not amount or amount <= 0:
                skipped += 1
                continue

            merchant = extract_merchant(sms.body) or sms.sender
            bank = detect_bank(sms.body, sms.sender) or sms.sender
            payment_method = detect_payment_rail(sms.body)
            direction = _detect_direction(sms.body)

            # === Step 5: Classify SPENDING CATEGORY ===
            from pipeline.category_classifier import classify_spending_category
            spending_cat, spending_conf = classify_spending_category(
                sms.body, merchant, direction
            )
            # Use spending category instead of generic 'financial_transaction'
            category = spending_cat
            confidence = spending_conf

            classified += 1
            categories[category] = categories.get(category, 0) + 1

            # UPI reference extraction
            upi_ref = None
            try:
                from pipeline.preprocessor import UPI_REF_PATTERN
                upi_match = UPI_REF_PATTERN.search(sms.body)
                if upi_match:
                    upi_ref = upi_match.group(1)
            except Exception:
                pass

            # === Step 6: Compute fingerprint ===
            fp_string = f"{sms.sender}|{sms.body}|{sms.timestamp}"
            fingerprint = hashlib.sha256(fp_string.encode()).hexdigest()

            # === Step 7: Fraud/anomaly scoring ===
            anomaly_score = 0.0
            try:
                from pipeline.fraud_detector import compute_anomaly_score
                anomaly_score = compute_anomaly_score(sms.body, amount, direction)
            except Exception:
                pass
                
            valid_txns.append({
                "sms": sms,
                "amount": amount,
                "direction": direction,
                "merchant": merchant,
                "bank": bank,
                "payment_method": payment_method,
                "category": category,
                "confidence": confidence,
                "anomaly_score": anomaly_score,
                "fingerprint": fingerprint,
                "upi_ref": upi_ref,
            })

        # === Phase 2: Batch LLM Extraction (100% Accurate Override) ===
        if valid_txns:
            try:
                from pipeline.llm_extractor import batch_extract_llm
                llm_results = await batch_extract_llm([t["sms"].body for t in valid_txns])
                for t, res in zip(valid_txns, llm_results):
                    # Override if LLM detected something useful
                    if res.get("merchant") and res.get("merchant").lower() != "unknown":
                        t["merchant"] = res["merchant"]
                    if res.get("category") and res.get("category").lower() != "uncategorized":
                        t["category"] = res["category"].lower().replace(' ', '_')
            except Exception as e:
                logger.error(f"Batch LLM extraction failed: {e}", exc_info=True)

        # === Phase 3: DB Insertion ===
        async with db_pool.acquire() as conn:
            for t in valid_txns:
                try:
                    await conn.execute(
                        """INSERT INTO transactions
                        (user_id, fingerprint, amount, direction, merchant, merchant_raw,
                         bank, payment_method, upi_ref, transaction_date, source,
                         category, category_confidence, anomaly_score, sync_mode)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::timestamptz,
                                'sms', $11, $12, $13, 'realtime')
                        ON CONFLICT (fingerprint) DO NOTHING""",
                        user.user_id, t["fingerprint"], t["amount"], t["direction"],
                        t["merchant"], t["sms"].body,
                        t["bank"], t["payment_method"], t["upi_ref"],
                        datetime.fromisoformat(t["sms"].date), t["category"], t["confidence"], t["anomaly_score"],
                    )
                    processed += 1
                except Exception as e:
                    logger.warning("Failed to insert SMS transaction: %s", e)

    except Exception as e:
        logger.error("SMS ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="SMS ingestion failed")

    elapsed_ms = int((time.time() - start) * 1000)

    logger.info(
        "SMS ingestion: received=%d, processed=%d, skipped=%d (non-txn), time=%dms",
        len(body.messages), processed, skipped, elapsed_ms,
    )

    return SmsIngestResponse(
        total_received=len(body.messages),
        total_processed=processed,
        total_classified=classified,
        total_skipped=skipped,
        categories=categories,
        processing_time_ms=elapsed_ms,
    )
