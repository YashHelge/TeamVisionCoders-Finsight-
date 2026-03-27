"""
Dataset API — JSON/CSV ingestion for hackathon/demo mode.
Accepts structured bank transactions and runs the full pipeline.
"""

import logging
import json
import csv
import io
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.dataset")


class DatasetTransaction(BaseModel):
    transaction_id: Optional[str] = None
    date: str
    description: str
    amount: float
    type: str  # debit | credit
    category: Optional[str] = None
    merchant: Optional[str] = None
    bank: Optional[str] = None
    payment_method: Optional[str] = None
    upi_ref: Optional[str] = None


class DatasetIngestRequest(BaseModel):
    transactions: List[DatasetTransaction]


class DatasetIngestResponse(BaseModel):
    total_received: int
    total_processed: int
    total_classified: int
    subscriptions_detected: int
    categories: dict
    processing_time_ms: int


@router.post("/dataset/ingest", response_model=DatasetIngestResponse)
async def ingest_dataset(
    request: Request,
    body: DatasetIngestRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Ingest structured bank transactions (JSON).
    Runs the full backend pipeline: classify, extract, detect subscriptions.
    No mobile app or SMS permissions required.
    """
    import time
    start = time.time()
    
    db_pool = request.app.state.db_pool
    redis_client = request.app.state.redis

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        processed = 0
        classified = 0
        categories = {}

        async with db_pool.acquire() as conn:
            for txn in body.transactions:
                # Generate fingerprint for dataset transactions
                import hashlib
                fp_string = f"{txn.amount:.2f}|{txn.description.lower().strip()}|{txn.date}|{txn.type}"
                fingerprint = hashlib.sha256(fp_string.encode()).hexdigest()

                # Classify
                category = txn.category
                confidence = 1.0
                if not category:
                    try:
                        from pipeline.labeler import rule_based_label
                        category, confidence = rule_based_label(txn.description)
                        if confidence < 0.80:
                            from pipeline.classifier import classify_text
                            category, confidence = await classify_text(txn.description)
                    except Exception:
                        category = "uncategorized"
                        confidence = 0.0

                classified += 1
                categories[category] = categories.get(category, 0) + 1

                # Extract merchant
                merchant = txn.merchant or txn.description.split()[0] if txn.description else "Unknown"
                try:
                    from pipeline.extractor import extract_merchant
                    merchant = extract_merchant(txn.description) or merchant
                except Exception:
                    pass

                # Insert into transactions table
                try:
                    await conn.execute(
                        """INSERT INTO transactions 
                        (user_id, fingerprint, amount, direction, merchant, merchant_raw,
                         bank, payment_method, upi_ref, transaction_date, source,
                         category, category_confidence, sync_mode)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::timestamptz,
                                'dataset', $11, $12, 'dataset')
                        ON CONFLICT (fingerprint) DO NOTHING""",
                        user.user_id, fingerprint, txn.amount, txn.type,
                        merchant, txn.description,
                        txn.bank, txn.payment_method, txn.upi_ref,
                        txn.date, category, confidence,
                    )
                    processed += 1
                except Exception as e:
                    logger.warning("Failed to insert transaction: %s", e)

        # Run subscription detection
        subs_detected = 0
        try:
            from subscription.dataset_ingestor import run_subscription_pipeline
            result = await run_subscription_pipeline(db_pool, redis_client, user.user_id)
            subs_detected = result.get("subscriptions_found", 0)
        except Exception as e:
            logger.warning("Subscription detection skipped: %s", e)

        elapsed_ms = int((time.time() - start) * 1000)

        return DatasetIngestResponse(
            total_received=len(body.transactions),
            total_processed=processed,
            total_classified=classified,
            subscriptions_detected=subs_detected,
            categories=categories,
            processing_time_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error("Dataset ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Dataset ingestion failed")


@router.post("/dataset/ingest/csv", response_model=DatasetIngestResponse)
async def ingest_csv(
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Ingest a CSV file of bank transactions."""
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    transactions = []
    for row in reader:
        transactions.append(DatasetTransaction(
            transaction_id=row.get("transaction_id"),
            date=row.get("date", ""),
            description=row.get("description", ""),
            amount=float(row.get("amount", 0)),
            type=row.get("type", "debit"),
            category=row.get("category"),
            merchant=row.get("merchant"),
            bank=row.get("bank"),
            payment_method=row.get("payment_method"),
        ))

    body = DatasetIngestRequest(transactions=transactions)
    return await ingest_dataset(request, body, user)
