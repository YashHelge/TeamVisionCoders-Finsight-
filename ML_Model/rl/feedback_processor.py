"""
RL Feedback Processor — Processes accumulated feedback into policy updates.
"""

import logging
from typing import List

from rl.bandit import ThompsonSamplingBandit

logger = logging.getLogger("finsight.rl.feedback_processor")


class FeedbackProcessor:
    """Processes batched feedback events into RL policy parameter updates."""

    def __init__(self, db_pool=None, redis_client=None):
        self.db_pool = db_pool
        self.redis = redis_client
        self.bandit = ThompsonSamplingBandit()

    async def process_pending_feedback(self, user_id: str) -> dict:
        """Process all unprocessed feedback for a user."""
        if not self.db_pool:
            return {"processed": 0}

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT id, policy_type, reward, context
                    FROM feedback_events
                    WHERE user_id = $1 AND processed = false
                    ORDER BY created_at ASC
                    LIMIT 100""",
                    user_id,
                )

                if not rows:
                    return {"processed": 0}

                classification_rewards = []
                subscription_rewards = []
                recommendation_rewards = []

                for row in rows:
                    policy_type = row["policy_type"]
                    reward = float(row["reward"])

                    if policy_type == "classification":
                        classification_rewards.append(reward)
                    elif policy_type == "subscription":
                        subscription_rewards.append(reward)
                    elif policy_type in ("recommendation", "engagement"):
                        recommendation_rewards.append(reward)

                # Update bandit for each policy type
                from rl.policy_manager import PolicyManager
                pm = PolicyManager(self.db_pool, self.redis)

                if classification_rewards:
                    policy = await pm.get_policy(user_id, "classification")
                    for reward in classification_rewards:
                        self.bandit.update(policy, reward)
                    await pm.update_policy(user_id, "classification", policy)

                if subscription_rewards:
                    policy = await pm.get_policy(user_id, "subscription")
                    for reward in subscription_rewards:
                        self.bandit.update(policy, reward)
                    await pm.update_policy(user_id, "subscription", policy)

                if recommendation_rewards:
                    policy = await pm.get_policy(user_id, "recommendation")
                    for reward in recommendation_rewards:
                        self.bandit.update(policy, reward)
                    await pm.update_policy(user_id, "recommendation", policy)

                # Mark as processed
                ids = [row["id"] for row in rows]
                await conn.execute(
                    "UPDATE feedback_events SET processed = true WHERE id = ANY($1::uuid[])",
                    ids,
                )

                logger.info(
                    "Processed %d feedback events for user %s (cls=%d, sub=%d, rec=%d)",
                    len(rows), user_id,
                    len(classification_rewards), len(subscription_rewards),
                    len(recommendation_rewards),
                )

                return {
                    "processed": len(rows),
                    "classification_updates": len(classification_rewards),
                    "subscription_updates": len(subscription_rewards),
                    "recommendation_updates": len(recommendation_rewards),
                }

        except Exception as e:
            logger.error("Feedback processing failed: %s", e)
            return {"processed": 0, "error": str(e)}
