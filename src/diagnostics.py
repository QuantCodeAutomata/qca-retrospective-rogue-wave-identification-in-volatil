"""Retrospective diagnostics; centered gradients here are not trading signals."""
import numpy as np
import pandas as pd
def _gradient(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError('Gradient input must be a finite one-dimensional array')
    if len(values) < 2:
        return np.full(len(values), np.nan)
    return np.gradient(values)


def compute_gradient_series(lambda_series: pd.Series) -> pd.Series:
    """Centered gradient for ex-post analysis (one-sided at endpoints).

    Interior values use the next observation and MUST NOT be used as live
    signals. The separate realtime pipeline recomputes a known ten-day block
    and timestamps the resulting warning at the end of that block.
    """
    return pd.Series(_gradient(lambda_series.to_numpy()),
                     index=lambda_series.index, name='gradient_lambda')


def compute_envelope_gradient(envelope: np.ndarray, dates: pd.DatetimeIndex,
                              window_L: int = 80) -> pd.Series:
    """Retrospective gradient of squared envelope, aligned to rolling windows."""
    envelope = np.asarray(envelope, dtype=float)
    if envelope.ndim != 1 or len(envelope) != len(dates):
        raise ValueError('Envelope and dates must be one-dimensional and aligned')
    if window_L < 1:
        raise ValueError('window_L must be positive')
    start = window_L - 1
    return pd.Series(_gradient(envelope[start:] ** 2),
                     index=pd.DatetimeIndex(dates[start:]), name='gradient_sq_envelope')


def assign_days_to_next_peak(dates: pd.DatetimeIndex,
                             peak_dates: pd.DatetimeIndex) -> pd.Series:
    """Exact observation distances to the next peak, including zero on peak day.

    ``dates`` is the complete observed trading calendar for the diagnostic
    interval, not a weekday approximation. After the last known peak, distance
    is unknown (NaN), not evidence that the next event is over 30 days away.
    """
    dates = pd.DatetimeIndex(dates)
    peaks = pd.DatetimeIndex(peak_dates).sort_values().unique()
    if dates.hasnans or not dates.is_monotonic_increasing or dates.has_duplicates:
        raise ValueError('dates must be a sorted unique trading calendar')
    if peaks.hasnans:
        raise ValueError('peak_dates cannot contain NaT')
    result = np.full(len(dates), np.nan)
    if not len(dates) or not len(peaks):
        return pd.Series(result, index=dates, name='days_to_next_peak')
    in_range = peaks[(peaks >= dates[0]) & (peaks <= dates[-1])]
    positions = dates.get_indexer(in_range)
    if (positions < 0).any():
        raise ValueError('Every in-range peak must occur on the observed calendar')
    next_idx = np.searchsorted(positions, np.arange(len(dates)), side='left')
    valid = next_idx < len(positions)
    result[valid] = positions[next_idx[valid]] - np.flatnonzero(valid)
    return pd.Series(result, index=dates, name='days_to_next_peak')


def bin_by_days_to_peak(days_series: pd.Series) -> pd.Series:
    """Paper Fig. 2 bins are strictly pre-peak: 0<d<=5, 5<d<=30, d>30.

    Peak-day and right-censored observations remain missing and are excluded
    from those distributions, rather than assigned to a different next peak.
    """
    days = pd.to_numeric(days_series, errors='raise')
    result = pd.Series(pd.NA, index=days.index, dtype='object', name=days.name)
    result.loc[(days > 0) & (days <= 5)] = '0-5'
    result.loc[(days > 5) & (days <= 30)] = '5-30'
    result.loc[days > 30] = '>30'
    return result
