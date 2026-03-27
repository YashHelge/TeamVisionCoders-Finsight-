"""
Batch Processor — Per-mode batch handling for sync operations.
"""

import logging
import hashlib
from typing import List

logger = logging.getLogger("finsight.sync.batch")


async def process_batch(
    db_pool,
    redis_client,
    user_id: str,
    signals: list,
    mode: str,
) -> List[str]:
    """
    Process a batch of signals through the ML pipeline and insert into DB.
    
    Mode-aware routing:
    - backfill: Run full pipeline on every record (DB is empty for this user).
    - catchup: Device already checked Zone B. Backend runs Bloom as safety net.
    - realtime: Steady state. Device pre-filtered OTPs/promos.
    
    Returns list of acknowledged fingerprints.
    """
    if not db_pool or not signals:
        return []

    acknowledged = []

    try:
        async with db_pool.acquire() as conn:
            for signal in signals:
                fp = signal.fingerprint if hasattr(signal, "fingerprint") else signal.get("fingerprint", "")
                payload = signal.payload_json if hasattr(signal, "payload_json") else signal.get("payload_json", "{}")
                ondevice_class = signal.ondevice_class if hasattr(signal, "ondevice_class") else signal.get("ondevice_class")
                ondevice_conf = signal.ondevice_conf if hasattr(signal, "ondevice_conf") else signal.get("ondevice_conf")
                source = signal.source if hasattr(signal, "source") else signal.get("source", "sms")

                try:
                    # Classify
                    category = ondevice_class or "uncategorized"
                    confidence = ondevice_conf or 0.0

                    # If on-device confidence is high enough, use it
                    if ondevice_conf and ondevice_conf >= 0.90 and ondevice_class:
                        category = ondevice_class
                        confidence = ondevice_conf
                    else:
                        # Run backend ML pipeline
                        try:
                            from pipeline.labeler import rule_based_label
                            from pipeline.classifier import classify_text
                            
                            category, confidence = rule_based_label(payload)
                            if confidence < 0.80:
                                category, confidence = await classify_text(payload)
                        except ImportError:
                            pass
                        except Exception as e:
                            logger.warning("ML classification failed: %s", e)

                    # Skip non-financial signals
                    if category in ("otp", "promotional", "personal", "spam") and confidence >= 0.85:
                        acknowledged.append(fp)
                        continue

                    # Extract transaction fields
                    amount = 0.0
                    direction = "debit"
                    merchant = "Unknown"
                    bank = None
                    payment_method = None
                    upi_ref = None
                    account_last4 = None
                    transaction_date = None
                    balance_after = None

                    try:
                        from pipeline.extractor import extract_transaction_fields
                        fields = extract_transaction_fields(payload)
                        amount = fields.get("amount", 0.0)
                        direction = fields.get("direction", "debit")
                        merchant = fields.get("merchant", "Unknown")
                        bank = fields.get("bank")
                        payment_method = fields.get("payment_method")
                        upi_ref = fields.get("upi_ref")
                        account_last4 = fields.get("account_last4")
                        transaction_date = fields.get("transaction_date")
                        balance_after = fields.get("balance_after")
                    except ImportError:
                        pass
                    except Exception as e:
                        logger.warning("Field extraction failed: %s", e)

                    if not transaction_date:
                        from datetime import datetime, timezone
                        transaction_date = datetime.now(timezone.utc).isoformat()

                    # Fraud scoring
                    fraud_score = 0.0
                    anomaly_score = 0.0
                    try:
                        from pipeline.fraud_detector import compute_fraud_score, compute_anomaly_score
                        fraud_score = compute_fraud_score(payload)
                        anomaly_score = await compute_anomaly_score(
                            db_pool, user_id, amount, merchant
                        )
                    except ImportError:
                        pass
                    except Exception:
                        pass

                    # Insert into transactions table
                    await conn.execute(
                        """INSERT INTO transactions 
                        (user_id, fingerprint, amount, direction, merchant, merchant_raw,
                         bank, payment_method, upi_ref, account_last4, transaction_date,
                         balance_after, source, category, category_confidence,
                         fraud_score, anomaly_score, sync_mode)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                                $11::timestamptz, $12, $13, $14, $15, $16, $17, $18)
                        ON CONFLICT (fingerprint) DO NOTHING""",
                        user_id, fp, amount, direction, merchant, payload,
                        bank, payment_method, upi_ref, account_last4,
                        transaction_date, balance_after, source,
                        category, confidence, fraud_score, anomaly_score, mode,
                    )

                    # Add to Bloom Filter
                    if redis_client:
                        try:
                            from sync.dedup_gate import add_to_bloom_filter
                            await add_to_bloom_filter(redis_client, user_id, [fp])
                        except Exception:
                            pass

                    acknowledged.append(fp)

                except Exception as e:
                    logger.error("Failed to process signal %s: %s", fp, e)

        # Update sync checkpoint count
        try:
            from sync.checkpoint_manager import increment_sync_count
            await increment_sync_count(db_pool, user_id, len(acknowledged), len(acknowledged))
        except Exception:
            pass

        # Invalidate analytics cache
        if redis_client and acknowledged:
            try:
                for period in ["7d", "30d", "90d", "1y", "all"]:
                    await redis_client.delete(f"analytics:{user_id}:{period}")
            except Exception:
                pass

    except Exception as e:
        logger.error("Batch processing failed: %s", e, exc_info=True)

    return acknowledged
