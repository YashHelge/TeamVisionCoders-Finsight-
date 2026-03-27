"""
Analytics API — Net flow, category breakdown, payment method distribution,
top merchants, and cash flow forecast.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from api.auth import CurrentUser, get_current_user
from config import settings

router = APIRouter()
logger = logging.getLogger("finsight.analytics")


class AnalyticsResponse(BaseModel):
    net_flow: float
    total_income: float
    total_expense: float
    category_breakdown: Dict[str, float]
    payment_method_distribution: Dict[str, float]
    top_merchants: List[Dict]
    daily_trend: List[Dict]
    forecast_7d: Optional[float] = None
    forecast_30d: Optional[float] = None
    period: str
    cached: bool = False


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    request: Request,
    period: str = Query("30d", regex="^(7d|30d|90d|1y|all)$"),
    user: CurrentUser = Depends(get_current_user),
):
    """Compute and return financial analytics for the user."""
    redis_client = request.app.state.redis
    db_pool = request.app.state.db_pool
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not available")

    # ── Check Redis cache ──
    cache_key = f"analytics:{user.user_id}:{period}"
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                data["cached"] = True
                return AnalyticsResponse(**data)
        except Exception:
            pass

    # ── Compute from DB ──
    period_map = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "all": 3650}
    days = period_map.get(period, 30)
    since = datetime.utcnow() - timedelta(days=days)

    try:
        async with db_pool.acquire() as conn:
            # Net flow
            row = await conn.fetchrow(
                """SELECT 
                    COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END), 0) as expense
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2""",
                user.user_id, since,
            )
            total_income = float(row["income"])
            total_expense = float(row["expense"])

            # Category breakdown (expenses by category)
            cat_rows = await conn.fetch(
                """SELECT category, COALESCE(SUM(amount), 0) as total
                FROM transactions 
                WHERE user_id = $1 AND direction='debit' AND transaction_date >= $2
                GROUP BY category ORDER BY total DESC""",
                user.user_id, since,
            )
            category_breakdown = {r["category"]: float(r["total"]) for r in cat_rows}

            # Payment method distribution
            pm_rows = await conn.fetch(
                """SELECT COALESCE(payment_method, 'unknown') as pm, COUNT(*) as cnt
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2
                GROUP BY pm ORDER BY cnt DESC""",
                user.user_id, since,
            )
            payment_method_distribution = {r["pm"]: int(r["cnt"]) for r in pm_rows}

            # Top merchants
            merch_rows = await conn.fetch(
                """SELECT merchant, COUNT(*) as txn_count, 
                          COALESCE(SUM(amount), 0) as total_amount
                FROM transactions 
                WHERE user_id = $1 AND direction='debit' AND transaction_date >= $2
                GROUP BY merchant ORDER BY total_amount DESC LIMIT 10""",
                user.user_id, since,
            )
            top_merchants = [
                {"merchant": r["merchant"], "txn_count": int(r["txn_count"]),
                 "total_amount": float(r["total_amount"])}
                for r in merch_rows
            ]

            # Daily trend
            trend_rows = await conn.fetch(
                """SELECT DATE(transaction_date) as day,
                    COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END), 0) as expense
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2
                GROUP BY day ORDER BY day""",
                user.user_id, since,
            )
            daily_trend = [
                {"date": str(r["day"]), "income": float(r["income"]),
                 "expense": float(r["expense"])}
                for r in trend_rows
            ]

        # Simple exponential smoothing forecast
        forecast_7d = None
        forecast_30d = None
        if len(daily_trend) >= 7:
            expenses = [d["expense"] for d in daily_trend[-30:]]
            alpha = 0.3
            smoothed = expenses[0]
            for e in expenses[1:]:
                smoothed = alpha * e + (1 - alpha) * smoothed
            forecast_7d = round(smoothed * 7, 2)
            forecast_30d = round(smoothed * 30, 2)

        result = AnalyticsResponse(
            net_flow=round(total_income - total_expense, 2),
            total_income=round(total_income, 2),
            total_expense=round(total_expense, 2),
            category_breakdown=category_breakdown,
            payment_method_distribution=payment_method_distribution,
            top_merchants=top_merchants,
            daily_trend=daily_trend,
            forecast_7d=forecast_7d,
            forecast_30d=forecast_30d,
            period=period,
            cached=False,
        )

        # Cache in Redis
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key, settings.ANALYTICS_CACHE_TTL, result.model_dump_json()
                )
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error("Analytics failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute analytics")


@router.delete("/analytics/cache")
async def invalidate_cache(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Invalidate analytics cache for the user (called after new transactions)."""
    redis_client = request.app.state.redis
    if redis_client:
        for period in ["7d", "30d", "90d", "1y", "all"]:
            await redis_client.delete(f"analytics:{user.user_id}:{period}")
    return {"status": "cache_invalidated"}
