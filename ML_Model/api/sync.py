"""
Sync API — Batch sync endpoint for all three modes (backfill, catchup, realtime).
"""

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user
from config import settings

router = APIRouter()
logger = logging.getLogger("finsight.sync")


class SignalPayload(BaseModel):
    fingerprint: str
    payload_json: str  # encrypted JSON
    ondevice_class: Optional[str] = None
    ondevice_conf: Optional[float] = None
    source: str = "sms"  # sms | notification | merged
    timestamp_ms: int = 0


class SyncBatchRequest(BaseModel):
    signals: List[SignalPayload]
    batch_id: Optional[str] = None
    device_id: Optional[str] = None


class SyncBatchResponse(BaseModel):
    batch_id: str
    acknowledged: List[str]
    rejected: List[str]
    model_version: str
    processing_time_ms: int


@router.post("/sync/batch", response_model=SyncBatchResponse)
async def sync_batch(
    request: Request,
    body: SyncBatchRequest,
    mode: str = Query(..., regex="^(backfill|catchup|realtime)$"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Receive a batch of signals from the device.
    
    Modes:
    - backfill: First install, DB empty. Run full pipeline on every record.
    - catchup: Re-install. Device pre-checked Zone B via /dedup/check.
    - realtime: Steady state. Device pre-filtered OTPs/promos.
    """
    start_time = time.time()
    db_pool = request.app.state.db_pool
    redis_client = request.app.state.redis

    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    acknowledged = []
    rejected = []
    batch_id = body.batch_id or f"batch_{int(time.time() * 1000)}"

    try:
        from sync.dedup_gate import check_and_insert_fingerprints
        from sync.batch_processor import process_batch

        # 1) Dedup gate: check fingerprints against Bloom Filter + PG
        new_fingerprints, duplicate_fingerprints = await check_and_insert_fingerprints(
            db_pool, redis_client, user.user_id, 
            [s.fingerprint for s in body.signals]
        )

        # Duplicates are acknowledged (device marks SYNCED) but not processed
        acknowledged.extend(duplicate_fingerprints)

        # 2) Process new signals through the full pipeline
        if new_fingerprints:
            new_signals = [s for s in body.signals if s.fingerprint in set(new_fingerprints)]
            processed = await process_batch(
                db_pool, redis_client, user.user_id, new_signals, mode
            )
            acknowledged.extend(processed)

    except Exception as e:
        logger.error("Sync batch failed for user %s: %s", user.user_id, e, exc_info=True)
        # Any signals not acknowledged can be retried by the device
        rejected = [s.fingerprint for s in body.signals if s.fingerprint not in acknowledged]

    elapsed_ms = int((time.time() - start_time) * 1000)

    return SyncBatchResponse(
        batch_id=batch_id,
        acknowledged=acknowledged,
        rejected=rejected,
        model_version=settings.TFLITE_MODEL_VERSION,
        processing_time_ms=elapsed_ms,
    )
