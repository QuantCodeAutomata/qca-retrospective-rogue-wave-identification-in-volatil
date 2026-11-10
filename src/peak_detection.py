"""Retrospective peak labels; full-sample prominences are ex-post quantities."""
import math
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_prominences

_COLUMNS = ['date', 'envelope_value', 'prominence', 'severity']


def _vector(x, name):
    if np.iscomplexobj(x):
        raise ValueError(f'{name} must be real-valued')
    a = np.asarray(x, dtype=float)
    if a.ndim != 1 or not np.all(np.isfinite(a)):
        raise ValueError(f'{name} must be finite and one-dimensional')
    return a


def detect_peaks_and_prominences(envelope: np.ndarray, find_peaks_kwargs: dict = None) -> tuple:
    """Local maxima and their prominences, honoring wlen for both operations."""
    a = _vector(envelope, 'envelope')
    kwargs = dict(find_peaks_kwargs or {})
    peaks, properties = find_peaks(a, **kwargs)
    if len(peaks) == 0:
        return np.array([], dtype=int), np.array([], dtype=float)
    if 'prominences' in properties:
        proms = properties['prominences']
    else:
        proms, _, _ = peak_prominences(a, peaks, wlen=kwargs.get('wlen'))
    return peaks, proms


def compute_swh(prominences: np.ndarray, top_fraction: float = 1/3) -> float:
    """Mean of the top ceil(N*top_fraction) nonnegative prominences.

    The paper specifies top one-third but not rounding; ceil is retained.
    No peaks => zero SWH and no rogue labels (rather than fabricated events).
    """
    proms = _vector(prominences, 'prominences')
    if np.any(proms < 0):
        raise ValueError('prominences must be nonnegative')
    if not np.isfinite(top_fraction) or not 0 < top_fraction <= 1:
        raise ValueError('top_fraction must be in (0, 1]')
    if len(proms) == 0:
        return 0.0
    count = math.ceil(len(proms) * top_fraction)
    return float(np.mean(np.sort(proms)[-count:]))


def classify_rogue_peaks(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    peak_indices: np.ndarray,
    prominences: np.ndarray,
    swh: float,
    threshold_lower: float = 2.0,
    threshold_major: float = 2.5,
) -> pd.DataFrame:
    """Disjoint severity labels: major >2.5*SWH, lower >2*SWH, else normal."""
    a = _vector(envelope, 'envelope')
    proms = _vector(prominences, 'prominences')
    indices = np.asarray(peak_indices)
    if indices.ndim != 1 or len(indices) != len(proms):
        raise ValueError('peak_indices and prominences must have equal lengths')
    if len(dates) != len(a):
        raise ValueError('dates and envelope must have equal lengths')
    if len(indices) and (not np.issubdtype(indices.dtype, np.integer)
                         or np.any(indices < 0) or np.any(indices >= len(a))):
        raise ValueError('peak_indices must be valid integer indices')
    if not np.isfinite(swh) or swh < 0 or np.any(proms < 0):
        raise ValueError('SWH and prominences must be finite and nonnegative')
    if (not np.isfinite(threshold_lower) or not np.isfinite(threshold_major)
            or not 0 < threshold_lower < threshold_major):
        raise ValueError('thresholds must satisfy 0 < lower < major')
    records = []
    for idx, prom in zip(indices, proms):
        severity = ('major' if swh > 0 and prom > threshold_major*swh
                    else 'lower' if swh > 0 and prom > threshold_lower*swh else 'normal')
        records.append(dict(date=dates[idx], envelope_value=a[idx], prominence=prom, severity=severity))
    return pd.DataFrame.from_records(records, columns=_COLUMNS)


def full_peak_analysis(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    swh_top_fraction: float = 1/3,
    threshold_lower: float = 2.0,
    threshold_major: float = 2.5,
    find_peaks_kwargs: dict = None,
) -> tuple:
    """Detect peaks, compute configurable SWH, and classify ex-post events."""
    peaks, proms = detect_peaks_and_prominences(envelope, find_peaks_kwargs)
    swh = compute_swh(proms, top_fraction=swh_top_fraction)
    return classify_rogue_peaks(dates, envelope, peaks, proms, swh,
                                threshold_lower, threshold_major), swh
