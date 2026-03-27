"""
Dataset Ingestor — Full subscription intelligence pipeline runner.

Can be triggered via API or run standalone:
    python -m subscription.dataset_ingestor --file data/dummy_transactions.json --demo
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("finsight.subscription.ingestor")


async def run_subscription_pipeline(
    db_pool,
    redis_client,
    user_id: str,
) -> Dict:
    """
    Run the full subscription detection pipeline for a user.
    
    Steps:
    1. Fetch all debit transactions from DB
    2. Normalize merchants
    3. Group by normalized merchant
    4. Detect periodicity per merchant group
    5. Cluster with HDBSCAN
    6. Categorize subscriptions
    7. Compute savings & waste scores
    8. Generate Cancel & Save recommendations
    9. Persist detected subscriptions to DB
    """
    if not db_pool:
        return {"error": "Database not available", "subscriptions_found": 0}

    try:
        # 1. Fetch transactions
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT merchant, amount, transaction_date, direction
                FROM transactions
                WHERE user_id = $1 AND direction = 'debit'
                ORDER BY transaction_date""",
                user_id,
            )

        if not rows:
            return {"subscriptions_found": 0, "message": "No debit transactions found"}

        # 2. Normalize merchants
        from subscription.normalizer import quick_normalize

        transactions: List[Dict] = []
        for r in rows:
            transactions.append({
                "merchant": quick_normalize(r["merchant"]),
                "merchant_raw": r["merchant"],
                "amount": float(r["amount"]),
                "date": r["transaction_date"],
            })

        # 3. Group by normalized merchant
        merchant_groups: Dict[str, List[Dict]] = {}
        for txn in transactions:
            merchant = txn["merchant"]
            merchant_groups.setdefault(merchant, []).append(txn)

        # 4. Detect periodicity per group
        from subscription.periodicity import detect_periodicity

        potential_subs = []
        for merchant, txns in merchant_groups.items():
            if len(txns) < 2:
                continue

            # Compute day offsets
            dates = sorted([t["date"] for t in txns])
            if isinstance(dates[0], str):
                from datetime import datetime as dt
                dates = [dt.fromisoformat(d.replace("Z", "+00:00")) if isinstance(d, str) else d for d in dates]

            first_date = dates[0]
            day_offsets = [(d - first_date).days for d in dates]
            amounts = [t["amount"] for t in txns]

            periodicity = detect_periodicity(day_offsets, amounts)

            if periodicity["is_periodic"]:
                potential_subs.append({
                    "merchant": merchant,
                    "avg_monthly_cost": sum(amounts) / max(len(amounts), 1),
                    "periodicity_days": periodicity["dominant_period_days"] or 30,
                    "periodicity_score": periodicity["periodicity_score"],
                    "first_seen": str(dates[0]) if dates else None,
                    "last_seen": str(dates[-1]) if dates else None,
                    "occurrence_count": len(txns),
                    "amount_cv": periodicity["amount_cv"],
                })

        if not potential_subs:
            return {"subscriptions_found": 0, "message": "No periodic patterns detected"}

        # 5. Cluster with HDBSCAN
        from subscription.clusterer import cluster_subscriptions, find_duplicate_subscriptions

        clusters = cluster_subscriptions(potential_subs)
        duplicates = find_duplicate_subscriptions(clusters)

        # 6. Categorize
        from subscription.categorizer import categorize_with_groq, categorize_local

        merchant_names = list(set(s["merchant"] for s in potential_subs))
        categories = {}
        for m in merchant_names:
            cat = categorize_local(m)
            if cat:
                categories[m] = cat

        uncategorized = [m for m in merchant_names if m not in categories]
        if uncategorized:
            try:
                groq_cats = await categorize_with_groq(uncategorized)
                categories.update(groq_cats)
            except Exception:
                for m in uncategorized:
                    categories[m] = "Other"

        for sub in potential_subs:
            sub["category"] = categories.get(sub["merchant"], "Other")

        # 7. Compute savings
        from subscription.savings import compute_savings

        enriched_subs = compute_savings(potential_subs)

        # 8. Generate recommendations
        from subscription.recommender import generate_recommendations

        recommendations = await generate_recommendations(enriched_subs)

        # Map recommendations back to subscriptions
        rec_map = {r.get("merchant"): r for r in recommendations}
        for sub in enriched_subs:
            rec = rec_map.get(sub["merchant"])
            if rec:
                sub["recommendation"] = json.dumps(rec)

        # 9. Persist to database
        async with db_pool.acquire() as conn:
            for sub in enriched_subs:
                await conn.execute(
                    """INSERT INTO subscriptions
                    (user_id, merchant, category, avg_monthly_cost, periodicity_days,
                     periodicity_score, first_seen, last_seen, occurrence_count,
                     waste_score, recommendation, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7::timestamptz, $8::timestamptz,
                            $9, $10, $11, TRUE)
                    ON CONFLICT ON CONSTRAINT subscriptions_pkey DO NOTHING""",
                    user_id, sub["merchant"], sub.get("category", "Other"),
                    sub.get("avg_monthly_cost", 0), sub.get("periodicity_days", 30),
                    sub.get("periodicity_score", 0),
                    sub.get("first_seen"), sub.get("last_seen"),
                    sub.get("occurrence_count", 0),
                    sub.get("waste_score", 0),
                    sub.get("recommendation"),
                )

        total_monthly = sum(s.get("monthly_cost", s.get("avg_monthly_cost", 0)) for s in enriched_subs)

        return {
            "subscriptions_found": len(enriched_subs),
            "total_monthly_cost": round(total_monthly, 2),
            "total_annual_cost": round(total_monthly * 12, 2),
            "categories": dict(categories),
            "duplicates_found": len(duplicates),
            "recommendations": len(recommendations),
        }

    except Exception as e:
        logger.error("Subscription pipeline failed: %s", e, exc_info=True)
        return {"error": str(e), "subscriptions_found": 0}


async def run_from_file(filepath: str) -> Dict:
    """Run pipeline from a JSON/CSV file (standalone demo mode)."""
    if not os.path.exists(filepath):
        return {"error": f"File not found: {filepath}"}

    with open(filepath, 'r') as f:
        if filepath.endswith('.csv'):
            import csv
            reader = csv.DictReader(f)
            data = list(reader)
        else:
            data = json.load(f)

    if not data:
        return {"error": "Empty file"}

    from subscription.normalizer import quick_normalize
    from subscription.periodicity import detect_periodicity
    from subscription.savings import compute_savings

    # Normalize and group
    merchant_groups: Dict[str, List] = {}
    for txn in data:
        merchant = quick_normalize(txn.get("description", txn.get("merchant", "Unknown")))
        amount = float(txn.get("amount", 0))
        date = txn.get("date", "")
        direction = txn.get("type", txn.get("direction", "debit"))

        if direction != "debit":
            continue

        merchant_groups.setdefault(merchant, []).append({
            "merchant": merchant, "amount": amount, "date": date,
        })

    # Detect periodicity
    potential_subs = []
    for merchant, txns in merchant_groups.items():
        if len(txns) < 2:
            continue

        dates = sorted(txns, key=lambda x: x["date"])
        try:
            parsed = [datetime.fromisoformat(d["date"]) for d in dates]
        except ValueError:
            for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
                try:
                    parsed = [datetime.strptime(d["date"], fmt) for d in dates]
                    break
                except ValueError:
                    continue
            else:
                continue

        first = parsed[0]
        day_offsets = [(d - first).days for d in parsed]
        amounts = [t["amount"] for t in txns]

        result = detect_periodicity(day_offsets, amounts)
        if result["is_periodic"]:
            potential_subs.append({
                "merchant": merchant,
                "avg_monthly_cost": sum(amounts) / len(amounts),
                "periodicity_days": result["dominant_period_days"] or 30,
                "periodicity_score": result["periodicity_score"],
                "first_seen": str(parsed[0]),
                "last_seen": str(parsed[-1]),
                "occurrence_count": len(txns),
            })

    enriched = compute_savings(potential_subs)

    return {
        "subscriptions_found": len(enriched),
        "subscriptions": enriched,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinSight Dataset Ingestor")
    parser.add_argument("--file", required=True, help="Path to JSON or CSV file")
    parser.add_argument("--demo", action="store_true", help="Run in demo mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_from_file(args.file))
    print(json.dumps(result, indent=2))
