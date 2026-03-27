"""
Checkpoint API — Bidirectional SyncCheckpoint GET/PUT.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.checkpoint")


class SyncCheckpointModel(BaseModel):
    user_id: str
    sync_mode: str = "UNINITIALIZED"  # UNINITIALIZED | BACKFILL | CATCHUP | REALTIME
    backfill_completed_at: Optional[str] = None
    last_synced_sms_date: Optional[str] = None
    oldest_sms_date_on_device: Optional[str] = None
    total_sms_synced: int = 0
    total_fingerprints: int = 0
    device_id: Optional[str] = None
    schema_version: int = 1
    updated_at: Optional[str] = None


@router.get("/sync/checkpoint", response_model=Optional[SyncCheckpointModel])
async def get_checkpoint(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Fetch remote SyncCheckpoint — called on app startup."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        from sync.checkpoint_manager import get_user_checkpoint
        checkpoint = await get_user_checkpoint(db_pool, user.user_id)
        return checkpoint
    except Exception as e:
        logger.error("Checkpoint fetch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch checkpoint")


@router.put("/sync/checkpoint", response_model=SyncCheckpointModel)
async def update_checkpoint(
    request: Request,
    body: SyncCheckpointModel,
    user: CurrentUser = Depends(get_current_user),
):
    """Write updated checkpoint after each successful sync batch."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # Ensure user can only update their own checkpoint
    if body.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Cannot update checkpoint for another user")

    try:
        from sync.checkpoint_manager import upsert_user_checkpoint
        result = await upsert_user_checkpoint(db_pool, body)
        return result
    except Exception as e:
        logger.error("Checkpoint update failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update checkpoint")
