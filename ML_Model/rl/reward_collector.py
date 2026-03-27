"""
RL Reward Collector — Collects implicit and explicit user feedback signals.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("finsight.rl.reward_collector")


class RewardCollector:
    """Collects rewards from user interactions for RL policy updates."""

    def __init__(self, db_pool=None, redis_client=None):
        self.db_pool = db_pool
        self.redis = redis_client

    async def record_category_correction(
        self, user_id: str, transaction_id: str,
        old_category: str, new_category: str,
    ) -> dict:
        """Record when user corrects an ML classification (explicit negative reward)."""
        reward = -1.0
        context = {
            "type": "category_correction",
            "old": old_category,
            "new": new_category,
            "transaction_id": transaction_id,
        }

        await self._store_feedback(user_id, "classification", reward, context)
        logger.info("Correction: %s → %s for user %s", old_category, new_category, user_id)
        return {"reward": reward, "action": "category_correction"}

    async def record_subscription_action(
        self, user_id: str, subscription_id: str, action: str,
    ) -> dict:
        """Record subscription action: cancel (+1), keep (0), remind_later (+0.3)."""
        reward_map = {"cancel": 1.0, "keep": 0.0, "remind_later": 0.3, "dismiss": -0.2}
        reward = reward_map.get(action, 0.0)

        context = {
            "type": "subscription_action",
            "subscription_id": subscription_id,
            "action": action,
        }

        await self._store_feedback(user_id, "subscription", reward, context)
        logger.info("Subscription action: %s (reward=%.1f) for user %s", action, reward, user_id)
        return {"reward": reward, "action": action}

    async def record_implicit_engagement(
        self, user_id: str, event_type: str, duration_ms: int = 0,
    ) -> dict:
        """Record implicit signals: screen time, scroll depth, chat interactions."""
        reward = min(duration_ms / 10000.0, 1.0)  # Normalize to [0, 1]

        context = {"type": "implicit", "event": event_type, "duration_ms": duration_ms}
        await self._store_feedback(user_id, "engagement", reward, context)
        return {"reward": reward, "event": event_type}

    async def _store_feedback(
        self, user_id: str, policy_type: str, reward: float, context: dict,
    ):
        """Persist feedback event to the database."""
        if not self.db_pool:
            return

        try:
            import json
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO feedback_events 
                    (user_id, policy_type, reward, context, created_at)
                    VALUES ($1, $2, $3, $4::jsonb, NOW())""",
                    user_id, policy_type, reward, json.dumps(context),
                )
        except Exception as e:
            logger.warning("Failed to store feedback: %s", e)
