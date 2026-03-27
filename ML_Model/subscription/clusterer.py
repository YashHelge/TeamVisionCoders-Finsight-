"""
HDBSCAN Clusterer — Density-based clustering for duplicate subscription detection.

6D feature space: [merchant_pca[0:3], periodicity_score, avg_amount_log, dominant_period_days]
"""

import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger("finsight.subscription.clusterer")


def cluster_subscriptions(subscriptions: List[Dict]) -> List[List[Dict]]:
    """
    Cluster subscriptions using HDBSCAN to surface duplicates.
    
    Input: list of subscription dicts with:
        - merchant (str)
        - periodicity_score (float)
        - avg_amount (float)  
        - dominant_period_days (int)
    
    Returns: list of clusters (each cluster is a list of subscription dicts)
    """
    if len(subscriptions) < 2:
        return [[s] for s in subscriptions]

    # Build 6D feature matrix
    features = _build_feature_matrix(subscriptions)

    try:
        import hdbscan

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=2,
            min_samples=1,
            metric='euclidean',
        )
        labels = clusterer.fit_predict(features)

    except ImportError:
        logger.info("HDBSCAN not available, falling back to simple distance clustering")
        labels = _simple_cluster(features)

    # Group by cluster label
    clusters: Dict[int, List[Dict]] = {}
    for i, label in enumerate(labels):
        # -1 = noise (treat each as own cluster)
        key = label if label >= 0 else -(i + 1000)
        clusters.setdefault(key, []).append(subscriptions[i])

    return list(clusters.values())


def _build_feature_matrix(subscriptions: List[Dict]) -> np.ndarray:
    """Build 6D feature matrix for clustering."""
    features = []

    # Get merchant embeddings (PCA to 3D)
    merchant_names = [s.get("merchant", "") for s in subscriptions]
    merchant_features = _merchant_to_features(merchant_names)

    for i, sub in enumerate(subscriptions):
        row = list(merchant_features[i])  # 3 dims from merchant PCA
        row.append(sub.get("periodicity_score", 0.0))  # dim 4
        row.append(np.log1p(sub.get("avg_amount", 0.0)))  # dim 5
        row.append(sub.get("dominant_period_days", 30) / 365.0)  # dim 6 (normalized)
        features.append(row)

    return np.array(features, dtype=float)


def _merchant_to_features(merchants: List[str]) -> np.ndarray:
    """Convert merchant names to 3D feature vectors."""
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.decomposition import PCA

        model = SentenceTransformer('all-MiniLM-L6-v2')
        embeddings = model.encode(merchants)

        n_components = min(3, len(merchants), embeddings.shape[1])
        pca = PCA(n_components=n_components)
        reduced = pca.fit_transform(embeddings)

        # Pad to 3 dims if needed
        if reduced.shape[1] < 3:
            padding = np.zeros((reduced.shape[0], 3 - reduced.shape[1]))
            reduced = np.hstack([reduced, padding])

        return reduced

    except ImportError:
        # Fallback: character-based features
        features = []
        for m in merchants:
            m_lower = m.lower()
            features.append([
                len(m) / 50.0,
                sum(c.isdigit() for c in m) / max(len(m), 1),
                hash(m_lower) % 1000 / 1000.0,
            ])
        return np.array(features)


def _simple_cluster(features: np.ndarray, threshold: float = 1.5) -> list:
    """Simple distance-based clustering fallback when HDBSCAN unavailable."""
    from scipy.spatial.distance import pdist, squareform

    if len(features) < 2:
        return list(range(len(features)))

    dist_matrix = squareform(pdist(features, 'euclidean'))
    labels = [-1] * len(features)
    current_label = 0

    for i in range(len(features)):
        if labels[i] >= 0:
            continue

        labels[i] = current_label
        for j in range(i + 1, len(features)):
            if labels[j] < 0 and dist_matrix[i][j] < threshold:
                labels[j] = current_label

        current_label += 1

    return labels


def find_duplicate_subscriptions(clusters: List[List[Dict]]) -> List[Dict]:
    """Identify potential duplicate subscriptions from clusters."""
    duplicates = []

    for cluster in clusters:
        if len(cluster) <= 1:
            continue

        # Sort by occurrence count (most established first)
        sorted_cluster = sorted(cluster, key=lambda x: x.get("occurrence_count", 0), reverse=True)

        primary = sorted_cluster[0]
        for dup in sorted_cluster[1:]:
            duplicates.append({
                "primary": primary.get("merchant"),
                "duplicate": dup.get("merchant"),
                "primary_cost": primary.get("avg_amount", 0),
                "duplicate_cost": dup.get("avg_amount", 0),
                "potential_saving": dup.get("avg_amount", 0),
            })

    return duplicates
