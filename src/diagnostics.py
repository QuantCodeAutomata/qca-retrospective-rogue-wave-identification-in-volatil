import numpy as np
import pandas as pd
from src.schrodinger import rolling_schrodinger_analysis


def compute_lambda_series(
    dates: pd.DatetimeIndex,
    envelope: np.ndarray,
    window_L: int = 80
) -> pd.Series:
    """Rolling |lambda_min| series."""
    df = rolling_schrodinger_analysis(dates, envelope, window_L)
    return pd.Series(df['abs_lambda_min'].values, index=df['date'], name='abs_lambda_min')


def compute_gradient_series(lambda_series: pd.Series) -> pd.Series:
    """Gradient of |lambda_min| via numpy.gradient."""
    grad = np.gradient(lambda_series.values)
    return pd.Series(grad, index=lambda_series.index, name='gradient_lambda')


def compute_envelope_gradient(
    envelope: np.ndarray,
    dates: pd.DatetimeIndex,
    window_L: int = 80
) -> pd.Series:
    """Gradient of squared envelope for comparison, starting at window_L-1."""
    sq_env = envelope ** 2
    start = window_L - 1
    sub = sq_env[start:]
    sub_dates = dates[start:]
    grad = np.gradient(sub)
    return pd.Series(grad, index=sub_dates, name='gradient_sq_envelope')


def assign_days_to_next_peak(
    dates: pd.DatetimeIndex,
    peak_dates: pd.DatetimeIndex
) -> pd.Series:
    """For each date, compute trading days to next peak. NaN if none."""
    peak_dates_sorted = pd.DatetimeIndex(sorted(peak_dates))
    result = []
    dates_arr = pd.DatetimeIndex(dates)
    for d in dates_arr:
        future_peaks = peak_dates_sorted[peak_dates_sorted > d]
        if len(future_peaks) == 0:
            result.append(np.nan)
        else:
            # count trading days between d and next peak
            next_peak = future_peaks[0]
            # use integer index difference in the dates array as proxy for trading days
            all_dates = dates_arr
            d_pos = all_dates.searchsorted(d)
            p_pos = all_dates.searchsorted(next_peak, side='left')
            result.append(float(p_pos - d_pos))
    return pd.Series(result, index=dates_arr, name='days_to_next_peak')


def bin_by_days_to_peak(days_series: pd.Series) -> pd.Series:
    """Bin days_to_next_peak into '0-5', '5-30', '>30'."""
    def _bin(d):
        if pd.isna(d):
            return '>30'
        d = float(d)
        if d <= 5:
            return '0-5'
        elif d <= 30:
            return '5-30'
        else:
            return '>30'
    return days_series.map(_bin)
