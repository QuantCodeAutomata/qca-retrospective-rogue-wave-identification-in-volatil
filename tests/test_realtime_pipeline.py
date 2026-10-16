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
