"""
Checkpoint Manager — Bidirectional SyncCheckpoint read/write to Supabase.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("finsight.sync.checkpoint")


async def get_user_checkpoint(db_pool, user_id: str) -> Optional[dict]:
    """Fetch checkpoint from Supabase user_sync_state table."""
    if not db_pool:
        return None

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_sync_state WHERE user_id = $1",
                user_id,
            )
        if row:
            return {
                "user_id": str(row["user_id"]),
                "sync_mode": row["sync_mode"],
                "backfill_completed_at": str(row["backfill_completed_at"]) if row["backfill_completed_at"] else None,
                "last_synced_sms_date": str(row["last_synced_sms_date"]) if row["last_synced_sms_date"] else None,
                "oldest_sms_date_on_device": str(row["oldest_sms_date_on_device"]) if row["oldest_sms_date_on_device"] else None,
                "total_sms_synced": row["total_sms_synced"],
                "total_fingerprints": row["total_fingerprints"],
                "device_id": str(row["device_id"]) if row["device_id"] else None,
                "schema_version": row["schema_version"],
                "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
            }
        return None
    except Exception as e:
        logger.error("Checkpoint fetch failed for user %s: %s", user_id, e)
        return None


async def upsert_user_checkpoint(db_pool, checkpoint) -> dict:
    """Insert or update checkpoint in Supabase user_sync_state table."""
    if not db_pool:
        raise RuntimeError("Database pool not available")

    # Handle both dict and Pydantic model
    if hasattr(checkpoint, "model_dump"):
        data = checkpoint.model_dump()
    elif isinstance(checkpoint, dict):
        data = checkpoint
    else:
        data = dict(checkpoint)

    now = datetime.now(timezone.utc).isoformat()

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO user_sync_state 
                (user_id, sync_mode, backfill_completed_at, last_synced_sms_date,
                 oldest_sms_date_on_device, total_sms_synced, total_fingerprints,
                 device_id, schema_version, updated_at)
                VALUES ($1, $2, $3::timestamptz, $4::timestamptz, $5::timestamptz,
                        $6, $7, $8::uuid, $9, $10::timestamptz)
                ON CONFLICT (user_id) DO UPDATE SET
                    sync_mode = EXCLUDED.sync_mode,
                    backfill_completed_at = COALESCE(EXCLUDED.backfill_completed_at, user_sync_state.backfill_completed_at),
                    last_synced_sms_date = EXCLUDED.last_synced_sms_date,
                    oldest_sms_date_on_device = COALESCE(EXCLUDED.oldest_sms_date_on_device, user_sync_state.oldest_sms_date_on_device),
                    total_sms_synced = EXCLUDED.total_sms_synced,
                    total_fingerprints = EXCLUDED.total_fingerprints,
                    device_id = COALESCE(EXCLUDED.device_id, user_sync_state.device_id),
                    schema_version = EXCLUDED.schema_version,
                    updated_at = EXCLUDED.updated_at""",
                data.get("user_id"),
                data.get("sync_mode", "UNINITIALIZED"),
                data.get("backfill_completed_at"),
                data.get("last_synced_sms_date"),
                data.get("oldest_sms_date_on_device"),
                data.get("total_sms_synced", 0),
                data.get("total_fingerprints", 0),
                data.get("device_id"),
                data.get("schema_version", 1),
                now,
            )

        data["updated_at"] = now
        return data

    except Exception as e:
        logger.error("Checkpoint upsert failed: %s", e, exc_info=True)
        raise


async def increment_sync_count(db_pool, user_id: str, count: int, fingerprint_count: int = 0):
    """Increment total_sms_synced and total_fingerprints after a batch."""
    if not db_pool:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE user_sync_state 
                SET total_sms_synced = total_sms_synced + $2,
                    total_fingerprints = total_fingerprints + $3,
                    updated_at = NOW()
                WHERE user_id = $1""",
                user_id, count, fingerprint_count,
            )
    except Exception as e:
        logger.warning("Sync count increment failed: %s", e)
