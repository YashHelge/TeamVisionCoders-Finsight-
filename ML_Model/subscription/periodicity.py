"""
Periodicity Detector — ACF, FFT, and Lomb-Scargle analysis.

Combined score = 0.40×ACF + 0.35×FFT + 0.25×LS
Confirmed if score ≥ 0.60 AND occurrences ≥ 2
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple

logger = logging.getLogger("finsight.subscription.periodicity")

TARGET_PERIODS = [7, 14, 28, 30, 31, 60, 90, 180, 365]


def detect_periodicity(timestamps_days: list, amounts: list = None) -> Dict:
    """
    Detect periodicity in a sequence of transaction timestamps.
    
    Args:
        timestamps_days: list of day offsets from first transaction
        amounts: optional list of amounts (for amount variability check)
    
    Returns dict with:
        - is_periodic: bool
        - dominant_period_days: int
        - periodicity_score: float (0.0 to 1.0)
        - acf_score: float
        - fft_score: float  
        - ls_score: float
        - amount_cv: float (coefficient of variation)
        - is_variable_amount: bool
    """
    if len(timestamps_days) < 2:
        return _no_periodicity()

    ts = np.array(sorted(timestamps_days), dtype=float)
    intervals = np.diff(ts)

    if len(intervals) < 1:
        return _no_periodicity()

    # ── ACF Analysis ──
    acf_score, acf_period = _acf_analysis(intervals)

    # ── FFT Analysis ──
    fft_score, fft_period = _fft_analysis(ts)

    # ── Lomb-Scargle (for sparse data) ──
    ls_score, ls_period = _lombscargle_analysis(ts)

    # Combined score
    combined = 0.40 * acf_score + 0.35 * fft_score + 0.25 * ls_score

    # Determine dominant period
    candidates = [(acf_period, acf_score), (fft_period, fft_score), (ls_period, ls_score)]
    candidates = [(p, s) for p, s in candidates if p is not None and p > 0]

    dominant_period = None
    if candidates:
        dominant_period = max(candidates, key=lambda x: x[1])[0]
        dominant_period = _snap_to_standard_period(dominant_period)

    # Amount variability
    amount_cv = 0.0
    is_variable = False
    if amounts and len(amounts) >= 2:
        amounts_arr = np.array(amounts, dtype=float)
        mean_amt = np.mean(amounts_arr)
        if mean_amt > 0:
            amount_cv = float(np.std(amounts_arr) / mean_amt)
            is_variable = amount_cv > 0.15

    is_periodic = combined >= 0.60 and len(timestamps_days) >= 2

    return {
        "is_periodic": is_periodic,
        "dominant_period_days": int(dominant_period) if dominant_period else None,
        "periodicity_score": round(float(combined), 4),
        "acf_score": round(float(acf_score), 4),
        "fft_score": round(float(fft_score), 4),
        "ls_score": round(float(ls_score), 4),
        "amount_cv": round(amount_cv, 4),
        "is_variable_amount": is_variable,
    }


def _acf_analysis(intervals: np.ndarray) -> Tuple[float, Optional[int]]:
    """ACF-based periodicity detection using lag peaks at standard periods."""
    if len(intervals) < 2:
        return 0.0, None

    mean_interval = np.mean(intervals)
    best_score = 0.0
    best_period = None

    for target in TARGET_PERIODS:
        deviations = np.abs(intervals - target)
        tolerance = max(target * 0.2, 2)
        matches = np.sum(deviations <= tolerance)
        score = matches / len(intervals)

        if score > best_score:
            best_score = score
            best_period = target

    # Also check median interval
    median_interval = np.median(intervals)
    for target in TARGET_PERIODS:
        if abs(median_interval - target) <= max(target * 0.15, 2):
            consistency = 1.0 - np.std(intervals) / max(np.mean(intervals), 1)
            consistency = max(0, min(1, consistency))
            score = max(best_score, 0.5 + 0.5 * consistency)
            if score > best_score:
                best_score = score
                best_period = target

    return min(best_score, 1.0), best_period


def _fft_analysis(timestamps: np.ndarray) -> Tuple[float, Optional[int]]:
    """FFT-based periodicity: dominant frequency ≥ 3σ above noise."""
    if len(timestamps) < 4:
        return 0.0, None

    try:
        intervals = np.diff(timestamps)
        if len(intervals) < 3:
            return 0.0, None

        # Create a regular signal from intervals
        signal = intervals - np.mean(intervals)
        fft_vals = np.abs(np.fft.rfft(signal))

        if len(fft_vals) < 2:
            return 0.0, None

        # Find dominant frequency
        magnitudes = fft_vals[1:]  # Skip DC component
        if len(magnitudes) == 0:
            return 0.0, None

        noise_level = np.mean(magnitudes)
        noise_std = np.std(magnitudes) if len(magnitudes) > 1 else 1.0

        peak_idx = np.argmax(magnitudes)
        peak_magnitude = magnitudes[peak_idx]

        # Score: how much the peak stands above noise
        if noise_std > 0:
            snr = (peak_magnitude - noise_level) / noise_std
            score = min(max(snr / 3.0, 0.0), 1.0)  # 3σ = 1.0
        else:
            score = 0.5

        # Estimate period from frequency
        freq_idx = peak_idx + 1
        if freq_idx > 0:
            period = len(intervals) * np.mean(intervals) / freq_idx
            period = _snap_to_standard_period(period)
        else:
            period = None

        return score, period

    except Exception as e:
        logger.debug("FFT analysis failed: %s", e)
        return 0.0, None


def _lombscargle_analysis(timestamps: np.ndarray) -> Tuple[float, Optional[int]]:
    """Lomb-Scargle periodogram for sparse/irregular data (< 8 points)."""
    if len(timestamps) < 3:
        return 0.0, None

    try:
        from scipy.signal import lombscargle

        t = timestamps - timestamps[0]
        y = np.ones_like(t)  # Binary signal (transaction happened)

        # Test frequencies corresponding to standard periods
        freqs = [2 * np.pi / p for p in TARGET_PERIODS if p < (t[-1] - t[0])]
        if not freqs:
            return 0.0, None

        freqs = np.array(freqs)
        power = lombscargle(t, y - np.mean(y), freqs, normalize=True)

        if len(power) == 0:
            return 0.0, None

        peak_idx = np.argmax(power)
        peak_power = power[peak_idx]
        period = TARGET_PERIODS[peak_idx] if peak_idx < len(TARGET_PERIODS) else None

        # Normalize score
        score = min(float(peak_power), 1.0)

        return score, period

    except Exception as e:
        logger.debug("Lomb-Scargle failed: %s", e)
        return 0.0, None


def _snap_to_standard_period(period: float) -> int:
    """Snap a detected period to the nearest standard subscription period."""
    if period is None or period <= 0:
        return 30  # Default monthly

    best = TARGET_PERIODS[0]
    best_dist = abs(period - best)

    for target in TARGET_PERIODS:
        dist = abs(period - target)
        if dist < best_dist:
            best = target
            best_dist = dist

    return best


def _no_periodicity() -> Dict:
    return {
        "is_periodic": False, "dominant_period_days": None,
        "periodicity_score": 0.0, "acf_score": 0.0,
        "fft_score": 0.0, "ls_score": 0.0,
        "amount_cv": 0.0, "is_variable_amount": False,
    }
