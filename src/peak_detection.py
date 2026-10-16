import math
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_prominences


def detect_peaks_and_prominences(
    envelope: np.ndarray,
    find_peaks_kwargs: dict = None
) -> tuple:
    """Detect local maxima and compute prominences. Returns (peak_indices, prominences)."""
    kwargs = find_peaks_kwargs or {}
    peaks, _ = find_peaks(envelope, **kwargs)
    if len(peaks) == 0:
        return np.array([], dtype=int), np.array([], dtype=float)
    proms, _, _ = peak_prominences(envelope, peaks)
    return peaks, proms


def compute_swh(prominences: np.ndarray) -> float:
    """SWH = mean of top ceil(N/3) prominences. N = number of peaks."""
    N = len(prominences)
    if N == 0:
        return 0.0
    top_count = math.ceil(N / 3)
    sorted_proms = np.sort(prominences)[::-1]
    return float(np.mean(sorted_proms[:top_count]))


def classify_rogue_peaks(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    peak_indices: np.ndarray,
    prominences: np.ndarray,
    swh: float,
    threshold_lower: float = 2.0,
    threshold_major: float = 2.5
) -> pd.DataFrame:
    """Classify peaks by severity. Returns DataFrame with date, envelope_value, prominence, severity."""
    records = []
    for idx, prom in zip(peak_indices, prominences):
        date = dates[idx]
        val = envelope[idx]
        if swh > 0 and prom > threshold_major * swh:
            severity = 'major'
        elif swh > 0 and prom > threshold_lower * swh:
            severity = 'lower'
        else:
            severity = 'normal'
        records.append({'date': date, 'envelope_value': val, 'prominence': prom, 'severity': severity})
    return pd.DataFrame(records)


def full_peak_analysis(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    swh_top_fraction: float = 1/3,
    threshold_lower: float = 2.0,
    threshold_major: float = 2.5,
    find_peaks_kwargs: dict = None
) -> tuple:
    """Detect peaks, compute SWH, classify. Returns (peak_df, swh)."""
    peaks, proms = detect_peaks_and_prominences(envelope, find_peaks_kwargs)
    swh = compute_swh(proms)
    peak_df = classify_rogue_peaks(dates, envelope, peaks, proms, swh, threshold_lower, threshold_major)
    return peak_df, swh
