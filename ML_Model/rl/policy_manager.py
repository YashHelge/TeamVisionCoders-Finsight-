"""
RL Policy Manager — Manages multiple RL policies per user.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("finsight.rl.policy_manager")


class PolicyManager:
    """Manages RL policies: classification, subscription, recommendation."""

    POLICY_TYPES = ["classification", "subscription", "recommendation"]

    def __init__(self, db_pool=None, redis_client=None):
        self.db_pool = db_pool
        self.redis = redis_client

    async def get_policy(self, user_id: str, policy_type: str) -> dict:
        """Get or create a user's RL policy parameters."""
        if policy_type not in self.POLICY_TYPES:
            return self._default_policy(policy_type)

        # Check Redis cache first
        if self.redis:
            cached = await self.redis.get(f"rl:policy:{user_id}:{policy_type}")
            if cached:
                return json.loads(cached)

        # Check database
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT parameters FROM rl_policies WHERE user_id = $1 AND policy_type = $2",
                        user_id, policy_type,
                    )
                    if row:
                        params = json.loads(row["parameters"])
                        # Cache in Redis
                        if self.redis:
                            await self.redis.setex(
                                f"rl:policy:{user_id}:{policy_type}",
                                3600, json.dumps(params),
                            )
                        return params
            except Exception as e:
                logger.warning("Policy fetch failed: %s", e)

        return self._default_policy(policy_type)

    async def update_policy(self, user_id: str, policy_type: str, parameters: dict):
        """Update a user's RL policy parameters."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO rl_policies (user_id, policy_type, parameters, updated_at)
                        VALUES ($1, $2, $3::jsonb, NOW())
                        ON CONFLICT (user_id, policy_type)
                        DO UPDATE SET parameters = $3::jsonb, updated_at = NOW()""",
                        user_id, policy_type, json.dumps(parameters),
                    )
            except Exception as e:
                logger.warning("Policy update failed: %s", e)

        # Update cache
        if self.redis:
            await self.redis.setex(
                f"rl:policy:{user_id}:{policy_type}",
                3600, json.dumps(parameters),
            )

    def _default_policy(self, policy_type: str) -> dict:
        """Default policy parameters for cold-start."""
        return {
            "alpha": [1.0] * 18,  # 18 categories
            "beta": [1.0] * 18,
            "total_updates": 0,
            "last_update": None,
        }
