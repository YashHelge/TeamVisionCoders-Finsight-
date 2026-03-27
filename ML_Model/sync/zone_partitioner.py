"""
Zone Partitioner — Condition 2 three-zone time partitioning logic.

Zone A: date < (last_synced - 7 days)  → Skip entirely
Zone B: (last_synced - 7 days) ≤ date ≤ last_synced  → Check each fingerprint
Zone C: date > last_synced  → Sync all
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from config import settings

logger = logging.getLogger("finsight.sync.zones")


class ZonePartition:
    """Represents the three time zones for Condition 2 (re-install) sync."""

    def __init__(
        self,
        last_synced_date: datetime,
        overlap_days: int = None,
    ):
        self.last_synced = last_synced_date
        self.overlap_days = overlap_days or settings.CATCHUP_OVERLAP_DAYS
        self.zone_b_start = last_synced_date - timedelta(days=self.overlap_days)

    def classify_timestamp(self, ts: datetime) -> str:
        """Classify a timestamp into Zone A, B, or C."""
        if ts < self.zone_b_start:
            return "A"
        elif ts <= self.last_synced:
            return "B"
        else:
            return "C"

    def partition_signals(self, signals: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Partition a list of signals into zones.
        
        Each signal dict must have a 'timestamp' or 'date' field.
        
        Returns: {"A": [...], "B": [...], "C": [...]}
        """
        zones = {"A": [], "B": [], "C": []}

        for signal in signals:
            ts = signal.get("timestamp") or signal.get("date")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    # Try parsing common formats
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            ts = datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
                            break
                        except ValueError:
                            continue
                    else:
                        # Can't parse → treat as Zone C (new, sync it)
                        zones["C"].append(signal)
                        continue

            if not isinstance(ts, datetime):
                zones["C"].append(signal)
                continue

            zone = self.classify_timestamp(ts)
            zones[zone].append(signal)

        logger.info(
            "Zone partition: A=%d (skip), B=%d (check), C=%d (sync all)",
            len(zones["A"]), len(zones["B"]), len(zones["C"]),
        )

        return zones


async def process_catchup_zones(
    db_pool,
    redis_client,
    user_id: str,
    signals: List[Dict],
    last_synced_date: datetime,
) -> Tuple[List[str], List[str]]:
    """
    Process signals using the three-zone strategy for Condition 2 (CATCHUP mode).
    
    Returns: (fingerprints_to_sync, fingerprints_skipped)
    """
    partitioner = ZonePartition(last_synced_date)
    zones = partitioner.partition_signals(signals)

    fingerprints_to_sync = []
    fingerprints_skipped = []

    # Zone A — Skip entirely (no network calls, no fingerprint computation)
    zone_a_count = len(zones["A"])
    fingerprints_skipped.extend([s.get("fingerprint", "") for s in zones["A"] if s.get("fingerprint")])
    logger.info("Zone A: Skipping %d signals (guaranteed in DB)", zone_a_count)

    # Zone B — Check each fingerprint against backend
    if zones["B"]:
        zone_b_fps = [s.get("fingerprint") for s in zones["B"] if s.get("fingerprint")]
        if zone_b_fps:
            from sync.dedup_gate import check_fingerprints_exist
            existence = await check_fingerprints_exist(db_pool, redis_client, user_id, zone_b_fps)

            for fp, exists in existence.items():
                if exists:
                    fingerprints_skipped.append(fp)
                else:
                    fingerprints_to_sync.append(fp)

            logger.info(
                "Zone B: %d present (skipped), %d absent (will sync)",
                sum(1 for v in existence.values() if v),
                sum(1 for v in existence.values() if not v),
            )

    # Zone C — Sync all (these are definitely new)
    zone_c_fps = [s.get("fingerprint") for s in zones["C"] if s.get("fingerprint")]
    fingerprints_to_sync.extend(zone_c_fps)
    logger.info("Zone C: %d signals to sync (definitely new)", len(zone_c_fps))

    return fingerprints_to_sync, fingerprints_skipped
