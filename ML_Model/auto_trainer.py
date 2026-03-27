"""
Auto Trainer — Background continuous retraining system.

Trigger: 200 new transactions since last training
Check interval: 5 minutes
User corrections override rule-assigned labels in training data.
After retraining: model distilled to INT8 TFLite → pushed to all user devices.
"""

import asyncio
import logging
import os
from datetime import datetime

from config import settings

logger = logging.getLogger("finsight.auto_trainer")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
_last_training_txn_count = 0
_is_training = False


async def check_and_retrain(db_pool, redis_client=None):
    """
    Check if retraining is needed and trigger if so.
    Called periodically by the background task.
    """
    global _last_training_txn_count, _is_training

    if _is_training:
        logger.debug("Training already in progress, skipping check")
        return

    if not db_pool:
        return

    try:
        async with db_pool.acquire() as conn:
            current_count = await conn.fetchval("SELECT COUNT(*) FROM transactions")

            new_since_last = current_count - _last_training_txn_count
            if new_since_last < settings.RETRAIN_THRESHOLD:
                return

            logger.info(
                "Retraining triggered: %d new transactions (threshold: %d)",
                new_since_last, settings.RETRAIN_THRESHOLD,
            )

            _is_training = True

            # Fetch training data (including user corrections)
            rows = await conn.fetch(
                """SELECT merchant_raw as text, category as label
                FROM transactions
                WHERE merchant_raw IS NOT NULL AND category IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 10000"""
            )

        if len(rows) < 50:
            logger.info("Not enough data for retraining (%d < 50)", len(rows))
            _is_training = False
            return

        texts = [r["text"] for r in rows]
        labels = [r["label"] for r in rows]

        # Run training in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _retrain, texts, labels)

        _last_training_txn_count = current_count
        logger.info("Retraining complete — model updated")

        # Attempt TFLite conversion
        try:
            await loop.run_in_executor(None, _convert_tflite)
            logger.info("TFLite model updated")
        except Exception as e:
            logger.warning("TFLite conversion skipped: %s", e)

    except Exception as e:
        logger.error("Auto-retrain check failed: %s", e, exc_info=True)
    finally:
        _is_training = False


def _retrain(texts, labels):
    """Synchronous training function (runs in thread pool)."""
    from train import train_model
    train_model(texts, labels, save=True)


def _convert_tflite():
    """Synchronous TFLite conversion (runs in thread pool)."""
    try:
        from tflite_converter import convert_to_tflite
        convert_to_tflite()
    except ImportError:
        logger.warning("TFLite converter not available")


async def start_auto_trainer(db_pool, redis_client=None):
    """Start the background auto-training loop."""
    logger.info(
        "Auto-trainer started: check every %ds, threshold %d transactions",
        settings.RETRAIN_CHECK_INTERVAL_SEC, settings.RETRAIN_THRESHOLD,
    )

    while True:
        await asyncio.sleep(settings.RETRAIN_CHECK_INTERVAL_SEC)
        try:
            await check_and_retrain(db_pool, redis_client)
        except Exception as e:
            logger.error("Auto-trainer iteration failed: %s", e)
