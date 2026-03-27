"""
RL Bandit — Thompson Sampling multi-armed bandit for personalized category ranking.

Each arm = category. Reward comes from user feedback (corrections, subscription actions).
Uses Beta(α, β) distribution for Thompson Sampling.
"""

import json
import logging
import math
import random
from typing import Dict, List, Optional, Tuple

from config import settings

logger = logging.getLogger("finsight.rl.bandit")


class ThompsonBandit:
    """Thompson Sampling bandit for category recommendation ranking."""

    def __init__(self, arms: List[str], alpha_init: float = None):
        self.arms = arms
        alpha = alpha_init or settings.RL_BANDIT_ALPHA
        self.params: Dict[str, Dict] = {
            arm: {"alpha": alpha, "beta": alpha, "pulls": 0, "total_reward": 0.0}
            for arm in arms
        }

    def select_arm(self) -> str:
        """Select arm via Thompson Sampling."""
        samples = {}
        for arm, p in self.params.items():
            samples[arm] = random.betavariate(max(p["alpha"], 0.1), max(p["beta"], 0.1))
        return max(samples, key=samples.get)

    def rank_arms(self) -> List[Tuple[str, float]]:
        """Rank all arms by Thompson sample. Returns [(arm, score), ...]."""
        samples = {}
        for arm, p in self.params.items():
            samples[arm] = random.betavariate(max(p["alpha"], 0.1), max(p["beta"], 0.1))
        return sorted(samples.items(), key=lambda x: x[1], reverse=True)

    def update(self, arm: str, reward: float):
        """Update arm parameters with observed reward."""
        if arm not in self.params:
            self.params[arm] = {"alpha": 0.5, "beta": 0.5, "pulls": 0, "total_reward": 0.0}

        p = self.params[arm]
        lr = settings.RL_LEARNING_RATE

        if reward > 0:
            p["alpha"] += lr * reward
        else:
            p["beta"] += lr * abs(reward)

        p["pulls"] += 1
        p["total_reward"] += reward

    def get_state(self) -> Dict:
        """Get serializable state."""
        return {
            "arms": self.arms,
            "params": self.params,
        }

    @classmethod
    def from_state(cls, state: Dict) -> "ThompsonBandit":
        """Restore from serialized state."""
        bandit = cls(state["arms"])
        bandit.params = state["params"]
        return bandit


async def get_user_bandit(db_pool, redis_client, user_id: str, arm_type: str = "category") -> ThompsonBandit:
    """Get or create a user's bandit for the given arm type."""
    cache_key = f"rl:{user_id}:{arm_type}"

    # Try Redis cache
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                state = json.loads(cached)
                return ThompsonBandit.from_state(state)
        except Exception:
            pass

    # Try database
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT bandit_state FROM rl_policies 
                    WHERE user_id = $1 AND arm_type = $2""",
                    user_id, arm_type,
                )
                if row and row["bandit_state"]:
                    state = json.loads(row["bandit_state"])
                    bandit = ThompsonBandit.from_state(state)

                    # Cache in Redis
                    if redis_client:
                        await redis_client.setex(cache_key, 3600, json.dumps(state))

                    return bandit
        except Exception as e:
            logger.warning("Bandit load failed: %s", e)

    # Create new bandit with default arms
    default_arms = _get_default_arms(arm_type)
    return ThompsonBandit(default_arms)


async def save_user_bandit(
    db_pool, redis_client, user_id: str, bandit: ThompsonBandit, arm_type: str = "category"
):
    """Persist bandit state to Redis and database."""
    state = bandit.get_state()
    state_json = json.dumps(state)
    cache_key = f"rl:{user_id}:{arm_type}"

    if redis_client:
        try:
            await redis_client.setex(cache_key, 3600, state_json)
        except Exception:
            pass

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO rl_policies (user_id, arm_type, bandit_state, updated_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id, arm_type) DO UPDATE 
                    SET bandit_state = EXCLUDED.bandit_state, updated_at = NOW()""",
                    user_id, arm_type, state_json,
                )
        except Exception as e:
            logger.warning("Bandit save failed: %s", e)


async def process_feedback(
    db_pool, redis_client, user_id: str,
    arm: str, reward: float, arm_type: str = "category",
):
    """Process user feedback and update the bandit."""
    bandit = await get_user_bandit(db_pool, redis_client, user_id, arm_type)
    bandit.update(arm, reward)
    await save_user_bandit(db_pool, redis_client, user_id, bandit, arm_type)
    logger.info("RL update: user=%s arm=%s reward=%.2f", user_id, arm, reward)


def _get_default_arms(arm_type: str) -> List[str]:
    """Default arms for different bandit types."""
    if arm_type == "category":
        return [
            "food_dining", "shopping", "transport", "entertainment",
            "utilities", "health", "education", "travel",
            "groceries", "rent_emi", "investment", "insurance",
            "personal_care", "gifts_donations", "subscriptions", "uncategorized",
        ]
    elif arm_type == "subscription":
        return ["cancel", "keep", "downgrade", "remind_later"]
    else:
        return ["option_a", "option_b", "option_c"]
