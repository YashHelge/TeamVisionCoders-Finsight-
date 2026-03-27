"""
Subscriptions API — CRUD, detection trigger, Cancel & Save recommendations.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger("finsight.subscriptions")


class SubscriptionModel(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    merchant: str
    category: str = "Other"
    avg_monthly_cost: float
    periodicity_days: int
    periodicity_score: float
    first_seen: str
    last_seen: str
    occurrence_count: int
    waste_score: Optional[float] = None
    recommendation: Optional[str] = None
    is_active: bool = True
    user_action: Optional[str] = None
    action_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubscriptionSummary(BaseModel):
    total_monthly_cost: float
    total_annual_cost: float
    active_count: int
    category_breakdown: dict
    subscriptions: List[SubscriptionModel]
    top_savings_opportunities: List[dict]


class SubscriptionActionRequest(BaseModel):
    subscription_id: str
    action: str  # cancel | keep | remind_later


@router.get("/subscriptions", response_model=SubscriptionSummary)
async def list_subscriptions(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Get all detected subscriptions with summary."""
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM subscriptions 
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY avg_monthly_cost DESC""",
                user.user_id,
            )

        subscriptions = [SubscriptionModel(**dict(r)) for r in rows]
        total_monthly = sum(s.avg_monthly_cost for s in subscriptions)

        # Category breakdown
        cat_breakdown = {}
        for s in subscriptions:
            cat_breakdown[s.category] = cat_breakdown.get(s.category, 0) + s.avg_monthly_cost

        # Top savings opportunities (by waste_score)
        savings_opps = sorted(
            [s for s in subscriptions if s.waste_score and s.waste_score > 0.3],
            key=lambda x: x.waste_score or 0,
            reverse=True,
        )[:5]

        return SubscriptionSummary(
            total_monthly_cost=round(total_monthly, 2),
            total_annual_cost=round(total_monthly * 12, 2),
            active_count=len(subscriptions),
            category_breakdown=cat_breakdown,
            subscriptions=subscriptions,
            top_savings_opportunities=[
                {
                    "merchant": s.merchant,
                    "monthly_cost": s.avg_monthly_cost,
                    "waste_score": s.waste_score,
                    "recommendation": s.recommendation,
                }
                for s in savings_opps
            ],
        )

    except Exception as e:
        logger.error("Subscriptions list failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch subscriptions")


@router.post("/subscriptions/detect")
async def detect_subscriptions(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Trigger full subscription detection pipeline for the user."""
    db_pool = request.app.state.db_pool
    redis_client = request.app.state.redis
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        from subscription.dataset_ingestor import run_subscription_pipeline
        result = await run_subscription_pipeline(db_pool, redis_client, user.user_id)
        return {"status": "detection_complete", **result}
    except Exception as e:
        logger.error("Subscription detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run subscription detection")


@router.post("/subscriptions/action")
async def subscription_action(
    request: Request,
    body: SubscriptionActionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    User takes action on a subscription — feeds RL reward signal.
    Actions: cancel (+1.0), keep (-0.5), remind_later (0.0)
    """
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    reward_map = {"cancel": 1.0, "keep": -0.5, "remind_later": 0.0}
    reward = reward_map.get(body.action, 0.0)

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE subscriptions 
                SET user_action = $1, action_at = NOW()
                WHERE id = $2::uuid AND user_id = $3""",
                body.action, body.subscription_id, user.user_id,
            )
            # Record RL feedback
            await conn.execute(
                """INSERT INTO feedback_events 
                (user_id, event_type, target_id, new_value, reward)
                VALUES ($1, 'subscription_action', $2::uuid, $3, $4)""",
                user.user_id, body.subscription_id, body.action, reward,
            )

        return {"status": "action_recorded", "action": body.action, "reward": reward}
    except Exception as e:
        logger.error("Subscription action failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record action")
