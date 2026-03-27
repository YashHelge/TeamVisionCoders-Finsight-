"""
Dedup API — Batch fingerprint lookup for Condition 2 Zone B.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.dedup")


class DedupCheckRequest(BaseModel):
    fingerprints: List[str]


class DedupCheckResponse(BaseModel):
    present: List[str]
    absent: List[str]


@router.post("/dedup/check", response_model=DedupCheckResponse)
async def dedup_check(
    request: Request,
    body: DedupCheckRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Batch fingerprint lookup against Bloom Filter.
    Used by Condition 2 (re-install) Zone B to pre-screen fingerprints
    before sending full payloads.
    """
    redis_client = request.app.state.redis
    db_pool = request.app.state.db_pool

    if not redis_client and not db_pool:
        raise HTTPException(status_code=503, detail="Neither Redis nor database available")

    present = []
    absent = []

    try:
        from sync.dedup_gate import check_fingerprints_exist

        results = await check_fingerprints_exist(
            db_pool, redis_client, user.user_id, body.fingerprints
        )
        for fp, exists in results.items():
            if exists:
                present.append(fp)
            else:
                absent.append(fp)

    except Exception as e:
        logger.error("Dedup check failed for user %s: %s", user.user_id, e, exc_info=True)
        # Fail-safe: treat all as absent (device will send full payloads, backend dedup catches them)
        absent = body.fingerprints

    return DedupCheckResponse(present=present, absent=absent)
