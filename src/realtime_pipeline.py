"""Expanding-prefix implementation of the paper's simulated realtime analysis.

An indicator is available only after the daily high on ``date`` is finalized.
``event_date`` is an explanatory location inside the known block, never an
execution timestamp. Past warnings are never revised using future data.
"""
import numpy as np
import pandas as pd
from src.signal_processing import process_series
from src.schrodinger import build_operator, solve_min_eigenpair


WARNING_COLUMNS = ['date', 'M_i', 'C_i', 'W_i', 'argmax_offset',
                   'event_date', 'date_max_grad']
BASELINE_COLUMNS = ['baseline_' + c for c in WARNING_COLUMNS if c != 'date']


def compute_envelope_at_day(x_history: np.ndarray,
                            percentile_threshold: float = 95.0,
                            filter_mode: str = 'spectral_peaks') -> np.ndarray:
    """Process only the currently available prefix through the full pipeline."""
    return process_series(x_history, percentile_threshold, filter_mode=filter_mode)


def compute_last10_lambda_block(envelope_history: np.ndarray, block_len: int = 10,
                                window_L: int = 80, boundary_condition: str = 'dirichlet',
                                delta_t: float = 1.0) -> tuple:
    """Compute the last ``block_len`` L-observation rolling eigenvalues.

    All windows include their endpoint j. The paper's notation j-L:j is
    ambiguous in indexing convention; this implementation consistently uses
    exactly L observations. A prefix of L+block_len-1 observations is enough.
    Missing initial windows are marked NaN; numerical failures propagate.
    """
    envelope_history = np.asarray(envelope_history, dtype=float)
    if (envelope_history.ndim != 1 or
            not np.isfinite(envelope_history).all()):
        raise ValueError('Envelope must be a finite one-dimensional array')
    if window_L < 3 or int(window_L) != window_L:
        raise ValueError('window_L must be an integer >= 3')
    if block_len < 2 or int(block_len) != block_len:
        raise ValueError('block_len must be an integer >= 2')
    window_L, block_len = int(window_L), int(block_len)
    if not np.isfinite(delta_t) or delta_t <= 0:
        raise ValueError('delta_t must be finite and positive')
    N = len(envelope_history)
    block_abs_lambda = np.full(block_len, np.nan)
    valid_mask = np.zeros(block_len, dtype=bool)
    for j in range(block_len):
        end_idx = N - block_len + j + 1
        start_idx = end_idx - window_L
        if start_idx < 0:
            continue
        window = envelope_history[start_idx:end_idx]
        H = build_operator(-window ** 2, boundary_condition=boundary_condition, delta_t=delta_t)
        lam, _ = solve_min_eigenpair(H)
        if not np.isfinite(lam):
            raise FloatingPointError('Eigenvalue solver returned a non-finite result')
        block_abs_lambda[j] = abs(lam)
        valid_mask[j] = True
    return block_abs_lambda, valid_mask


def compute_warning_indicator(block_abs_lambda: np.ndarray,
                              threshold_grad_count: float = 50) -> tuple:
    """Return M, C, W=M*C and gradient-maximum offset from a complete block.

    The maximum is of the SIGNED numerical gradient, not its absolute value.
    Centered differences inside this block use only data already known at the
    current signal date. Zero-filling failed/missing eigenvalues is forbidden:
    it manufactures gradient jumps and converts errors into apparently valid
    signals. Short or incomplete blocks raise ValueError.
    """
    block = np.asarray(block_abs_lambda, dtype=float)
    if block.ndim != 1 or len(block) < 2 or not np.isfinite(block).all():
        raise ValueError('Warning requires at least two finite eigenvalues')
    if not np.isfinite(threshold_grad_count) or threshold_grad_count < 0:
        raise ValueError('threshold_grad_count must be finite and nonnegative')
    grad = np.gradient(block)
    M_i = float(np.max(grad))
    C_i = int(np.count_nonzero(grad > threshold_grad_count))
    W_i = float(M_i * C_i) if C_i else 0.0
    # Only an inactive, numerically flat block has no resolvable location.
    # Choose its first coordinate deterministically without rounding M/C/W.
    # This is a diagnostic tie convention, not a change to alarm thresholds.
    flat_tolerance = 64 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(block))))
    offset = 0 if C_i == 0 and np.ptp(block) <= flat_tolerance else int(np.argmax(grad))
    return M_i, C_i, W_i, offset


def compute_rolling_max_block(envelope_history, block_len=10, window_L=80,
                              boundary_condition='dirichlet'):
    """Same-window maximum squared envelope control; no eigenvalue solver.

    The observed endpoint potentials are excluded under endpoint Dirichlet,
    exactly as in build_operator. This is a separate comparator, not an
    asserted mathematical identity with the eigenvalue.
    """
    envelope = np.asarray(envelope_history, dtype=float)
    if envelope.ndim != 1 or not np.isfinite(envelope).all() or (envelope < 0).any():
        raise ValueError('Envelope must be a finite nonnegative vector')
    for name, value, minimum in [('window_L', window_L, 3), ('block_len', block_len, 2)]:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
            raise ValueError(f'{name} must be an integer >= {minimum}')
    if boundary_condition not in {'dirichlet', 'dirichlet_ghost'}:
        raise ValueError('unsupported boundary_condition')
    if len(envelope) < window_L + block_len - 1:
        raise ValueError('A complete rolling maximum block is required')
    block = []
    for end in range(len(envelope) - block_len + 1, len(envelope) + 1):
        window = envelope[end-window_L:end]
        retained = window[1:-1] if boundary_condition == 'dirichlet' else window
        block.append(float(np.max(retained ** 2)))
    return np.asarray(block)


def run_realtime_simulation(series: pd.Series, percentile_threshold: float = 95.0,
                            window_L: int = 80, block_len: int = 10,
                            threshold_grad_count: float = 50,
                            progress: bool = True, filter_mode: str = 'spectral_peaks',
                            boundary_condition: str = 'dirichlet',
                            delta_t: float = 1.0, baseline: str | None = None) -> pd.DataFrame:
    """Past-only simulation, with one stored warning per eligible daily prefix.

    Failures are raised with their signal date. They are never disguised as a
    valid zero warning. Inputs require a sorted, unique observed calendar.
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError('series must have a DatetimeIndex')
    dates = series.index
    values = series.to_numpy(dtype=float)
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('series dates must be sorted and unique')
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Daily highs must be finite and strictly positive')
    if int(window_L) != window_L or window_L < 3:
        raise ValueError('window_L must be an integer >= 3')
    if int(block_len) != block_len or block_len < 2:
        raise ValueError('block_len must be an integer >= 2')
    if not np.isfinite(threshold_grad_count) or threshold_grad_count < 0:
        raise ValueError('threshold_grad_count must be finite and nonnegative')
    if not np.isfinite(percentile_threshold) or not 0 <= percentile_threshold <= 100:
        raise ValueError('percentile_threshold must lie in [0, 100]')
    window_L, block_len = int(window_L), int(block_len)
    if not np.isfinite(delta_t) or delta_t <= 0:
        raise ValueError('delta_t must be finite and positive')
    if boundary_condition not in {'dirichlet', 'dirichlet_ghost'}:
        raise ValueError('unsupported boundary_condition')
    if baseline not in {None, 'rolling_max'}:
        raise ValueError('baseline must be None or rolling_max')
    N = len(values)
    min_start = window_L + block_len - 2  # zero-based index of L+B-1 observations
    records = []
    for i in range(min_start, N):
        if progress and (i - min_start) % 100 == 0:
            print(f'  Real-time day {i-min_start+1}/{N-min_start} ({dates[i].date()})')
        try:
            envelope = compute_envelope_at_day(values[:i+1], percentile_threshold, filter_mode)
            block_lam, valid_mask = compute_last10_lambda_block(
                envelope, block_len, window_L, boundary_condition, delta_t)
            if not valid_mask.all():
                raise ValueError('An eligible prefix produced an incomplete eigenvalue block')
            M_i, C_i, W_i, argmax_off = compute_warning_indicator(block_lam, threshold_grad_count)
            if baseline is not None:
                control_block = compute_rolling_max_block(envelope, block_len, window_L, boundary_condition)
                bm, bc, bw, boff = compute_warning_indicator(control_block, threshold_grad_count)
        except Exception as exc:
            raise RuntimeError(f'Realtime computation failed on {dates[i]}') from exc
        event_idx = i - block_len + 1 + argmax_off
        record = {'date': dates[i], 'M_i': M_i, 'C_i': C_i, 'W_i': W_i,
                  'argmax_offset': argmax_off, 'event_date': dates[event_idx],
                  'date_max_grad': dates[event_idx]}
        if baseline is not None:
            bdate = dates[i - block_len + 1 + boff]
            record.update(baseline_M_i=bm, baseline_C_i=bc, baseline_W_i=bw,
                          baseline_argmax_offset=boff, baseline_event_date=bdate,
                          baseline_date_max_grad=bdate)
        records.append(record)
    return pd.DataFrame.from_records(records, columns=WARNING_COLUMNS + (BASELINE_COLUMNS if baseline else []))
