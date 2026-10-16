import numpy as np
import pandas as pd
from src.signal_processing import process_series
from src.schrodinger import build_operator, solve_min_eigenpair


def compute_envelope_at_day(
    x_history: np.ndarray,
    percentile_threshold: float = 95.0
) -> np.ndarray:
    """Process expanding history through full envelope pipeline."""
    return process_series(x_history, percentile_threshold)


def compute_last10_lambda_block(
    envelope_history: np.ndarray,
    block_len: int = 10,
    window_L: int = 80
) -> tuple:
    """For last block_len days, compute |lambda_min| for 80-day windows.
    Returns (block_abs_lambda, valid_mask).
    """
    N = len(envelope_history)
    block_abs_lambda = np.full(block_len, np.nan)
    valid_mask = np.zeros(block_len, dtype=bool)
    for j in range(block_len):
        # j=0 -> index N-block_len, j=block_len-1 -> index N-1
        end_idx = N - block_len + j + 1  # exclusive slice end
        start_idx = end_idx - window_L
        if start_idx < 0:
            continue
        window = envelope_history[start_idx:end_idx]
        if len(window) < window_L:
            continue
        U = -window ** 2
        try:
            H = build_operator(U)
            lam, _ = solve_min_eigenpair(H)
            block_abs_lambda[j] = abs(lam)
            valid_mask[j] = True
        except Exception:
            pass
    return block_abs_lambda, valid_mask


def compute_warning_indicator(
    block_abs_lambda: np.ndarray,
    threshold_grad_count: int = 50
) -> tuple:
    """Compute M_i, C_i, W_i, argmax_offset from block lambda values."""
    valid = ~np.isnan(block_abs_lambda)
    if valid.sum() < 2:
        return 0.0, 0, 0.0, 0
    # fill nans for gradient (use only valid prefix or interpolate)
    block = block_abs_lambda.copy()
    # replace nans with 0 for gradient
    block[~valid] = 0.0
    grad = np.gradient(block)
    M_i = float(np.max(grad))
    C_i = int(np.sum(grad > threshold_grad_count))
    W_i = M_i * C_i
    argmax_offset = int(np.argmax(grad))
    return M_i, C_i, W_i, argmax_offset


def run_realtime_simulation(
    series: pd.Series,
    percentile_threshold: float = 95.0,
    window_L: int = 80,
    block_len: int = 10,
    threshold_grad_count: int = 50
) -> pd.DataFrame:
    """Expanding-sample real-time simulation. Returns DataFrame with date, M_i, C_i, W_i, event_date."""
    dates = series.index
    values = series.values.astype(float)
    N = len(values)
    min_start = window_L + block_len - 1  # first eligible index
    records = []
    for i in range(min_start, N):
        if (i - min_start) % 100 == 0:
            print(f'  Real-time simulation day {i-min_start+1}/{N-min_start} ({dates[i].date()})')
        x_hist = values[:i+1]
        try:
            envelope = compute_envelope_at_day(x_hist, percentile_threshold)
            block_lam, valid_mask = compute_last10_lambda_block(envelope, block_len, window_L)
            M_i, C_i, W_i, argmax_off = compute_warning_indicator(block_lam, threshold_grad_count)
        except Exception as e:
            M_i, C_i, W_i, argmax_off = 0.0, 0, 0.0, 0
        # event_date: date in last block corresponding to argmax_offset
        event_idx = max(0, i - block_len + 1 + argmax_off)
        event_idx = min(event_idx, len(dates) - 1)
        records.append({
            'date': dates[i],
            'M_i': M_i,
            'C_i': C_i,
            'W_i': W_i,
            'argmax_offset': argmax_off,
            'event_date': dates[event_idx],
        })
    return pd.DataFrame(records)
