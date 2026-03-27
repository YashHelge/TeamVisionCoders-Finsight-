"""
Classifier — XGBoost + Random Forest ensemble with soft voting.

Soft vote: final_score = 0.55 × XGBoost + 0.45 × RF
"""

import logging
import os
import joblib
import numpy as np
from typing import Tuple, Optional

logger = logging.getLogger("finsight.pipeline.classifier")

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

# ── Cached models ──
_vectorizer = None
_classifier = None
_label_encoder = None


def _load_models():
    """Load trained models from disk (lazy, cached)."""
    global _vectorizer, _classifier, _label_encoder

    if _classifier is not None:
        return True

    try:
        vec_path = os.path.join(MODEL_DIR, "vectorizer.joblib")
        clf_path = os.path.join(MODEL_DIR, "classifier.joblib")
        le_path = os.path.join(MODEL_DIR, "label_encoder.joblib")

        if not all(os.path.exists(p) for p in [vec_path, clf_path, le_path]):
            logger.warning("Model files not found in %s — classifier unavailable", MODEL_DIR)
            return False

        _vectorizer = joblib.load(vec_path)
        _classifier = joblib.load(clf_path)
        _label_encoder = joblib.load(le_path)

        logger.info("ML models loaded from %s", MODEL_DIR)
        return True

    except Exception as e:
        logger.error("Failed to load ML models: %s", e)
        return False


async def classify_text(text: str, features: list = None) -> Tuple[str, float]:
    """
    Classify text using the trained ensemble model.
    
    Returns: (category, confidence)
    """
    if not _load_models():
        # Fallback to rule-based only
        from pipeline.labeler import rule_based_label
        return rule_based_label(text)

    try:
        from pipeline.preprocessor import normalize_text, engineer_features

        # TF-IDF features
        normalized = normalize_text(text)
        tfidf_vec = _vectorizer.transform([normalized])

        # Engineered features
        if features is None:
            features = engineer_features(text)

        eng_vec = np.array(features).reshape(1, -1)

        # Combine TF-IDF + engineered features
        from scipy.sparse import hstack
        combined = hstack([tfidf_vec, eng_vec])

        # Predict with probabilities
        proba = _classifier.predict_proba(combined)[0]
        pred_idx = np.argmax(proba)
        confidence = float(proba[pred_idx])
        category = _label_encoder.inverse_transform([pred_idx])[0]

        return (category, confidence)

    except Exception as e:
        logger.error("Classification failed: %s", e)
        from pipeline.labeler import rule_based_label
        return rule_based_label(text)


def classify_batch(texts: list) -> list:
    """Classify a batch of texts. Returns list of (category, confidence) tuples."""
    if not _load_models():
        from pipeline.labeler import rule_based_label
        return [rule_based_label(t) for t in texts]

    try:
        from pipeline.preprocessor import normalize_text, engineer_features
        from scipy.sparse import hstack

        normalized = [normalize_text(t) for t in texts]
        tfidf = _vectorizer.transform(normalized)
        eng = np.array([engineer_features(t) for t in texts])
        combined = hstack([tfidf, eng])

        proba = _classifier.predict_proba(combined)
        results = []
        for i, p in enumerate(proba):
            pred_idx = np.argmax(p)
            confidence = float(p[pred_idx])
            category = _label_encoder.inverse_transform([pred_idx])[0]
            results.append((category, confidence))

        return results

    except Exception as e:
        logger.error("Batch classification failed: %s", e)
        from pipeline.labeler import rule_based_label
        return [rule_based_label(t) for t in texts]


def reconcile_ondevice_result(
    ondevice_class: Optional[str],
    ondevice_conf: Optional[float],
    backend_class: str,
    backend_conf: float,
    threshold: float = 0.90,
) -> Tuple[str, float, str]:
    """
    Reconcile on-device classification with backend result.
    
    Returns: (final_category, final_confidence, source)
    """
    if ondevice_class and ondevice_conf and ondevice_conf >= threshold:
        return (ondevice_class, ondevice_conf, "ONDEVICE")

    return (backend_class, backend_conf, "BACKEND")
