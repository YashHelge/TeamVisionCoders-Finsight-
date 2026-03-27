"""
RL Subscription Policy — Manages subscription-specific RL decisions.
"""

import logging
from typing import List, Dict

logger = logging.getLogger("finsight.rl.subscription_policy")


class SubscriptionPolicy:
    """RL policy for subscription recommendations: Cancel vs Keep vs Remind."""

    ACTION_CANCEL = "cancel"
    ACTION_KEEP = "keep"
    ACTION_REMIND = "remind_later"

    def __init__(self, db_pool=None, redis_client=None):
        self.db_pool = db_pool
        self.redis = redis_client

    async def rank_recommendations(
        self, user_id: str, subscriptions: List[Dict],
    ) -> List[Dict]:
        """Rank subscription recommendations by predicted user action probability."""
        from rl.policy_manager import PolicyManager
        pm = PolicyManager(self.db_pool, self.redis)
        policy = await pm.get_policy(user_id, "subscription")

        total_updates = policy.get("total_updates", 0)

        # Cold start: rank by waste score
        if total_updates < 10:
            return sorted(subscriptions, key=lambda s: s.get("waste_score", 0), reverse=True)

        # Warm: use Thompson Sampling scores to personalize ranking
        import random
        for sub in subscriptions:
            waste = sub.get("waste_score", 0.5)
            alpha = policy.get("alpha", [1.0])[0]
            beta = policy.get("beta", [1.0])[0]
            # Sample from Beta distribution
            score = random.betavariate(alpha, beta)
            sub["rl_score"] = score * waste
            sub["rl_action"] = self._predict_action(score, waste)

        return sorted(subscriptions, key=lambda s: s.get("rl_score", 0), reverse=True)

    def _predict_action(self, rl_score: float, waste_score: float) -> str:
        """Predict the best recommendation action based on RL + waste score."""
        combined = (rl_score + waste_score) / 2
        if combined > 0.7:
            return self.ACTION_CANCEL
        elif combined > 0.4:
            return self.ACTION_REMIND
        else:
            return self.ACTION_KEEP

    async def get_savings_potential(self, user_id: str, subscriptions: List[Dict]) -> Dict:
        """Calculate total savings potential based on RL-ranked recommendations."""
        ranked = await self.rank_recommendations(user_id, subscriptions)

        cancel_savings = sum(
            s.get("monthly_cost", 0)
            for s in ranked
            if s.get("rl_action") == self.ACTION_CANCEL
        )
        remind_savings = sum(
            s.get("monthly_cost", 0) * 0.3  # Potential partial savings
            for s in ranked
            if s.get("rl_action") == self.ACTION_REMIND
        )

        return {
            "total_monthly_savings": cancel_savings + remind_savings,
            "cancel_count": sum(1 for s in ranked if s.get("rl_action") == self.ACTION_CANCEL),
            "remind_count": sum(1 for s in ranked if s.get("rl_action") == self.ACTION_REMIND),
            "keep_count": sum(1 for s in ranked if s.get("rl_action") == self.ACTION_KEEP),
        }
