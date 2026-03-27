"""
Sync Orchestrator — Mode selection and routing logic.

Selects between BACKFILL, CATCHUP, and REALTIME modes
based on checkpoint state.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("finsight.sync.orchestrator")


class SyncMode(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    BACKFILL = "BACKFILL"
    CATCHUP = "CATCHUP"
    REALTIME = "REALTIME"


async def determine_sync_mode(
    db_pool,
    user_id: str,
    device_checkpoint: Optional[dict] = None,
) -> SyncMode:
    """
    Determine the sync mode for a user based on checkpoint state.
    
    Decision tree:
    1. UNINITIALIZED + no remote checkpoint → BACKFILL (Condition 1)
    2. UNINITIALIZED + remote checkpoint exists with backfill_completed → CATCHUP (Condition 2)
    3. BACKFILL with backfill_completed_at = null → Resume BACKFILL
    4. BACKFILL/CATCHUP completed → REALTIME (Condition 3)
    5. Already REALTIME → stay REALTIME
    """
    from sync.checkpoint_manager import get_user_checkpoint

    # Fetch remote checkpoint
    remote = await get_user_checkpoint(db_pool, user_id)

    if remote is None:
        # No remote record — true first install
        logger.info("User %s: No remote checkpoint — BACKFILL mode", user_id)
        return SyncMode.BACKFILL

    remote_mode = remote.get("sync_mode", "UNINITIALIZED") if isinstance(remote, dict) else getattr(remote, "sync_mode", "UNINITIALIZED")
    backfill_completed = remote.get("backfill_completed_at") if isinstance(remote, dict) else getattr(remote, "backfill_completed_at", None)

    if remote_mode == SyncMode.REALTIME:
        return SyncMode.REALTIME

    if remote_mode == SyncMode.BACKFILL and backfill_completed is None:
        # Resume interrupted backfill
        logger.info("User %s: Resuming interrupted BACKFILL", user_id)
        return SyncMode.BACKFILL

    if backfill_completed is not None:
        # Local is UNINITIALIZED (re-install) but remote has completed backfill
        if device_checkpoint is None or device_checkpoint.get("sync_mode") == "UNINITIALIZED":
            logger.info("User %s: Re-install detected — CATCHUP mode", user_id)
            return SyncMode.CATCHUP
        return SyncMode.REALTIME

    # Default to BACKFILL for safety
    return SyncMode.BACKFILL


async def route_batch(
    db_pool,
    redis_client,
    user_id: str,
    signals: list,
    mode: str,
):
    """Route a batch of signals to the appropriate processor."""
    from sync.batch_processor import process_batch
    return await process_batch(db_pool, redis_client, user_id, signals, mode)
