"""
Dedup Gate — Two-level deduplication: Redis Bloom Filter + PostgreSQL UNIQUE constraint.

Level 1: Redis Bloom Filter per-user (O(1) lookup, 0.001% false positive rate)
Level 2: PostgreSQL UNIQUE(fingerprint) with ON CONFLICT DO NOTHING
"""

import logging
from typing import Dict, List, Tuple

from config import settings

logger = logging.getLogger("finsight.sync.dedup")


def _bloom_key(user_id: str) -> str:
    return f"dedup:{user_id}"


async def check_fingerprints_exist(
    db_pool,
    redis_client,
    user_id: str,
    fingerprints: List[str],
) -> Dict[str, bool]:
    """
    Check which fingerprints already exist.
    Used by /dedup/check endpoint (Condition 2 Zone B).
    
    Returns dict mapping fingerprint → exists (True/False).
    """
    results = {fp: False for fp in fingerprints}

    # Level 1: Redis Bloom Filter
    if redis_client:
        try:
            bloom_key = _bloom_key(user_id)
            for fp in fingerprints:
                # BF.EXISTS returns 1 if the item may exist, 0 if it definitely does not
                try:
                    exists = await redis_client.execute_command("BF.EXISTS", bloom_key, fp)
                    if exists:
                        results[fp] = True
                except Exception:
                    # Bloom filter may not exist yet — fall through to DB check
                    pass
        except Exception as e:
            logger.warning("Bloom Filter check failed: %s — falling back to DB", e)

    # Level 2: For any fingerprints not confirmed by Bloom, verify against PostgreSQL
    unconfirmed = [fp for fp, exists in results.items() if not exists]
    if unconfirmed and db_pool:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT fingerprint FROM transactions 
                    WHERE user_id = $1 AND fingerprint = ANY($2)""",
                    user_id, unconfirmed,
                )
                db_fps = {r["fingerprint"] for r in rows}
                for fp in unconfirmed:
                    if fp in db_fps:
                        results[fp] = True
                        # Add to Bloom Filter for future lookups
                        if redis_client:
                            try:
                                await redis_client.execute_command(
                                    "BF.ADD", _bloom_key(user_id), fp
                                )
                            except Exception:
                                pass
        except Exception as e:
            logger.warning("DB fingerprint check failed: %s", e)

    return results


async def check_and_insert_fingerprints(
    db_pool,
    redis_client,
    user_id: str,
    fingerprints: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Check and gate fingerprints for sync/batch endpoint.
    
    Returns: (new_fingerprints, duplicate_fingerprints)
    """
    if not fingerprints:
        return [], []

    # Check existing
    existence = await check_fingerprints_exist(db_pool, redis_client, user_id, fingerprints)

    new_fps = [fp for fp, exists in existence.items() if not exists]
    dup_fps = [fp for fp, exists in existence.items() if exists]

    logger.info(
        "Dedup gate for user %s: %d new, %d duplicates out of %d total",
        user_id, len(new_fps), len(dup_fps), len(fingerprints),
    )

    return new_fps, dup_fps


async def add_to_bloom_filter(redis_client, user_id: str, fingerprints: List[str]):
    """Add fingerprints to the user's Bloom Filter after successful insert."""
    if not redis_client or not fingerprints:
        return

    bloom_key = _bloom_key(user_id)
    try:
        # Ensure Bloom Filter exists
        try:
            await redis_client.execute_command(
                "BF.RESERVE", bloom_key,
                settings.BLOOM_ERROR_RATE,
                settings.BLOOM_CAPACITY,
            )
        except Exception:
            pass  # Already exists

        # Add all fingerprints
        for fp in fingerprints:
            await redis_client.execute_command("BF.ADD", bloom_key, fp)

    except Exception as e:
        logger.warning("Bloom Filter add failed: %s", e)


async def rebuild_bloom_filters(db_pool, redis_client):
    """
    Rebuild Bloom Filters from the transactions table on backend startup.
    Until rebuilt, duplicate protection falls back to PostgreSQL constraint.
    """
    if not db_pool or not redis_client:
        return

    try:
        async with db_pool.acquire() as conn:
            # Get all users with transactions
            users = await conn.fetch(
                "SELECT DISTINCT user_id FROM transactions"
            )

            for user_row in users:
                user_id = str(user_row["user_id"])
                bloom_key = _bloom_key(user_id)

                # Delete existing Bloom Filter and recreate
                try:
                    await redis_client.delete(bloom_key)
                except Exception:
                    pass

                try:
                    await redis_client.execute_command(
                        "BF.RESERVE", bloom_key,
                        settings.BLOOM_ERROR_RATE,
                        settings.BLOOM_CAPACITY,
                    )
                except Exception:
                    pass

                # Load all fingerprints for this user
                fps = await conn.fetch(
                    "SELECT fingerprint FROM transactions WHERE user_id = $1",
                    user_id,
                )

                # Bulk add to Bloom Filter
                for fp_row in fps:
                    try:
                        await redis_client.execute_command(
                            "BF.ADD", bloom_key, fp_row["fingerprint"]
                        )
                    except Exception:
                        pass

                logger.info(
                    "Rebuilt Bloom Filter for user %s: %d fingerprints",
                    user_id, len(fps),
                )

    except Exception as e:
        logger.error("Bloom Filter rebuild failed: %s", e, exc_info=True)
