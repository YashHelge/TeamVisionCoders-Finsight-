"""
Analytics Engine — Net flow, category breakdown, payment method distribution,
top merchants, and cash flow forecast (7d/30d exponential smoothing).
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("finsight.pipeline.analytics")


async def compute_analytics(
    db_pool,
    user_id: str,
    days: int = 30,
) -> Dict:
    """Compute comprehensive financial analytics for a user."""
    if not db_pool:
        return _empty_analytics()

    since = datetime.utcnow() - timedelta(days=days)

    try:
        async with db_pool.acquire() as conn:
            # Aggregate totals
            totals = await conn.fetchrow(
                """SELECT 
                    COUNT(*) as txn_count,
                    COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END), 0) as expense
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2""",
                user_id, since,
            )

            # Category breakdown
            categories = await conn.fetch(
                """SELECT category, 
                    COUNT(*) as cnt, 
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions 
                WHERE user_id = $1 AND direction='debit' AND transaction_date >= $2
                GROUP BY category ORDER BY total DESC""",
                user_id, since,
            )

            # Payment method distribution
            payment_methods = await conn.fetch(
                """SELECT COALESCE(payment_method, 'unknown') as method, 
                    COUNT(*) as cnt,
                    COALESCE(SUM(amount), 0) as total
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2
                GROUP BY method ORDER BY cnt DESC""",
                user_id, since,
            )

            # Top merchants by amount
            merchants = await conn.fetch(
                """SELECT merchant, COUNT(*) as txn_count, 
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(AVG(amount), 0) as avg_amount
                FROM transactions 
                WHERE user_id = $1 AND direction='debit' AND transaction_date >= $2
                GROUP BY merchant ORDER BY total_amount DESC LIMIT 15""",
                user_id, since,
            )

            # Daily spending trend
            daily = await conn.fetch(
                """SELECT DATE(transaction_date) as day,
                    COALESCE(SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END), 0) as expense,
                    COUNT(*) as txn_count
                FROM transactions 
                WHERE user_id = $1 AND transaction_date >= $2
                GROUP BY day ORDER BY day""",
                user_id, since,
            )

        income = float(totals["income"])
        expense = float(totals["expense"])

        # Exponential smoothing forecast
        daily_expenses = [float(d["expense"]) for d in daily]
        forecast_7d, forecast_30d = _exponential_forecast(daily_expenses)

        # Spending velocity (current vs previous period)
        velocity = await _compute_velocity(db_pool, user_id, days)

        return {
            "txn_count": totals["txn_count"],
            "total_income": round(income, 2),
            "total_expense": round(expense, 2),
            "net_flow": round(income - expense, 2),
            "savings_rate": round(((income - expense) / income * 100) if income > 0 else 0, 1),
            "spending_velocity": velocity,
            "categories": [
                {
                    "name": c["category"],
                    "total": round(float(c["total"]), 2),
                    "count": c["cnt"],
                    "avg": round(float(c["avg_amount"]), 2),
                    "pct": round(float(c["total"]) / expense * 100, 1) if expense > 0 else 0,
                }
                for c in categories
            ],
            "payment_methods": [
                {
                    "method": p["method"],
                    "count": p["cnt"],
                    "total": round(float(p["total"]), 2),
                }
                for p in payment_methods
            ],
            "top_merchants": [
                {
                    "merchant": m["merchant"],
                    "txn_count": m["txn_count"],
                    "total": round(float(m["total_amount"]), 2),
                    "avg": round(float(m["avg_amount"]), 2),
                }
                for m in merchants
            ],
            "daily_trend": [
                {
                    "date": str(d["day"]),
                    "income": round(float(d["income"]), 2),
                    "expense": round(float(d["expense"]), 2),
                    "txn_count": d["txn_count"],
                }
                for d in daily
            ],
            "forecast_7d": forecast_7d,
            "forecast_30d": forecast_30d,
        }

    except Exception as e:
        logger.error("Analytics computation failed: %s", e, exc_info=True)
        return _empty_analytics()


def _exponential_forecast(daily_expenses: List[float], alpha: float = 0.3) -> tuple:
    """
    Simple exponential smoothing forecast.
    Returns: (forecast_7d, forecast_30d)
    """
    if len(daily_expenses) < 3:
        return (None, None)

    smoothed = daily_expenses[0]
    for e in daily_expenses[1:]:
        smoothed = alpha * e + (1 - alpha) * smoothed

    return (round(smoothed * 7, 2), round(smoothed * 30, 2))


async def _compute_velocity(db_pool, user_id: str, days: int) -> Optional[float]:
    """
    Compute spending velocity: ratio of current period spending vs previous period.
    > 1.0 means spending more, < 1.0 means spending less.
    """
    try:
        now = datetime.utcnow()
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        async with db_pool.acquire() as conn:
            current = await conn.fetchval(
                """SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE user_id = $1 AND direction = 'debit'
                AND transaction_date >= $2""",
                user_id, current_start,
            )
            previous = await conn.fetchval(
                """SELECT COALESCE(SUM(amount), 0) FROM transactions
                WHERE user_id = $1 AND direction = 'debit'
                AND transaction_date >= $2 AND transaction_date < $3""",
                user_id, previous_start, current_start,
            )

        current = float(current)
        previous = float(previous)

        if previous > 0:
            return round(current / previous, 2)
        return None

    except Exception:
        return None


def _empty_analytics() -> Dict:
    return {
        "txn_count": 0, "total_income": 0, "total_expense": 0,
        "net_flow": 0, "savings_rate": 0, "spending_velocity": None,
        "categories": [], "payment_methods": [], "top_merchants": [],
        "daily_trend": [], "forecast_7d": None, "forecast_30d": None,
    }
