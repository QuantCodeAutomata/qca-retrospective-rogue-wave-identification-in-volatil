import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from src.realtime_pipeline import (
    compute_envelope_at_day, compute_last10_lambda_block,
    compute_warning_indicator
)


def make_synthetic_history(N=150):
    np.random.seed(42)
    t = np.linspace(0, 10 * np.pi, N)
    return 20 + 5 * np.sin(t) + np.random.normal(0, 0.3, N)


def test_compute_envelope_at_day_length():
    x = make_synthetic_history(100)
    env = compute_envelope_at_day(x)
    assert len(env) == len(x)


def test_compute_envelope_at_day_nonneg():
    x = make_synthetic_history(80)
    env = compute_envelope_at_day(x)
    assert np.all(env >= 0)


def test_compute_last10_lambda_block_shape():
    x = make_synthetic_history(120)
    env = compute_envelope_at_day(x)
    block_lam, valid_mask = compute_last10_lambda_block(env, block_len=10, window_L=80)
    assert len(block_lam) == 10
    assert len(valid_mask) == 10


def test_compute_warning_indicator_types():
    # Simple lambda block
    block = np.array([10.0, 12.0, 15.0, 20.0, 30.0, 35.0, 40.0, 42.0, 44.0, 45.0])
    M_i, C_i, W_i, argmax_off = compute_warning_indicator(block, threshold_grad_count=5)
    assert isinstance(M_i, float)
    assert isinstance(C_i, int)
    assert isinstance(W_i, float)
    assert isinstance(argmax_off, int)


def test_compute_warning_indicator_W_formula():
    block = np.array([10.0, 12.0, 20.0, 35.0, 40.0, 42.0, 43.0, 44.0, 44.5, 45.0])
    M_i, C_i, W_i, _ = compute_warning_indicator(block, threshold_grad_count=5)
    assert abs(W_i - M_i * C_i) < 1e-10


def test_compute_warning_indicator_all_low():
    # all gradients < threshold -> C_i == 0 -> W_i == 0
    block = np.array([10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9])
    M_i, C_i, W_i, _ = compute_warning_indicator(block, threshold_grad_count=50)
    assert C_i == 0
    assert W_i == 0.0


def test_compute_warning_indicator_monotone():
    # Monotone increasing block: gradient is roughly constant
    block = np.arange(10, dtype=float) * 10  # [0,10,20,...,90]
    M_i, C_i, W_i, argmax_off = compute_warning_indicator(block, threshold_grad_count=5)
    # gradient of linear series is constant; M_i should equal the gradient value
    grad = np.gradient(block)
    expected_M = float(np.max(grad))
    assert abs(M_i - expected_M) < 1e-10


def test_missing_eigenvalue_never_zero_filled():
    with pytest.raises(ValueError, match='finite'):
        compute_warning_indicator(np.array([np.nan, 100., 200.]))


def test_negative_gradient_does_not_become_positive_warning():
    block = np.arange(10, dtype=float)[::-1] * 100
    maximum, count, warning, _ = compute_warning_indicator(block)
    assert maximum == -100
    assert count == 0
    assert warning == 0


def test_first_eligible_prefix_and_event_timestamp():
    from src.realtime_pipeline import run_realtime_simulation
    dates = pd.bdate_range('2020-01-01', periods=89)
    series = pd.Series(make_synthetic_history(89), index=dates)
    result = run_realtime_simulation(series, progress=False)
    assert len(result) == 1
    assert result.date.iloc[0] == dates[88]
    assert dates[79] <= result.event_date.iloc[0] <= dates[88]
    assert result.date_max_grad.iloc[0] == result.event_date.iloc[0]
    assert run_realtime_simulation(series.iloc[:-1], progress=False).empty


def test_causal_prefix_invariance_and_future_shock():
    from src.realtime_pipeline import run_realtime_simulation
    dates = pd.bdate_range('2020-01-01', periods=105)
    values = make_synthetic_history(105)
    series = pd.Series(values, index=dates)
    short = run_realtime_simulation(series.iloc[:95], progress=False)
    future_shock = series.copy()
    future_shock.iloc[95:] *= 7
    longer = run_realtime_simulation(future_shock, progress=False)
    pd.testing.assert_frame_equal(short, longer.iloc[:len(short)].reset_index(drop=True))


def test_realtime_solver_failure_is_not_disguised_as_no_alert(monkeypatch):
    import src.realtime_pipeline as pipeline
    def broken(*args, **kwargs):
        raise np.linalg.LinAlgError('test failure')
    monkeypatch.setattr(pipeline, 'solve_min_eigenpair', broken)
    series = pd.Series(make_synthetic_history(89),
                       index=pd.bdate_range('2020-01-01', periods=89))
    with pytest.raises(RuntimeError, match='Realtime computation failed'):
        pipeline.run_realtime_simulation(series, progress=False)


def test_invalid_input_order_rejected():
    from src.realtime_pipeline import run_realtime_simulation
    series = pd.Series(make_synthetic_history(90),
                       index=pd.bdate_range('2020-01-01', periods=90))
    with pytest.raises(ValueError, match='sorted'):
        run_realtime_simulation(series.iloc[::-1], progress=False)
