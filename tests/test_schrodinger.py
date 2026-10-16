import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from src.schrodinger import (
    build_operator, solve_min_eigenpair, compute_width,
    compute_localization_distance, compute_potential_moments,
    rolling_schrodinger_analysis
)


L = 10  # small window for tests


def make_U(L, val=0.0):
    return np.full(L, val)


def test_build_operator_symmetry():
    U = make_U(L)
    H = build_operator(U)
    np.testing.assert_array_almost_equal(H, H.T)


def test_build_operator_size():
    U = make_U(L)
    H = build_operator(U)
    assert H.shape == (L - 2, L - 2)


def test_build_operator_tridiagonal():
    U = make_U(L, val=0.0)
    H = build_operator(U, delta_t=1.0)
    M = L - 2
    for i in range(M - 1):
        assert abs(H[i, i+1] - (-0.5)) < 1e-12
        assert abs(H[i+1, i] - (-0.5)) < 1e-12


def test_build_operator_diagonal():
    U = np.arange(L, dtype=float)
    H = build_operator(U, delta_t=1.0)
    interior = U[1:L-1]
    M = L - 2
    for i in range(M):
        expected_diag = 1.0 + interior[i]  # kinetic = 1/(dt^2) = 1 with dt=1
        assert abs(H[i, i] - expected_diag) < 1e-10


def test_solve_min_eigenpair_returns_tuple():
    U = make_U(L)
    H = build_operator(U)
    result = solve_min_eigenpair(H)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_solve_min_eigenpair_eigenvalue_real():
    U = make_U(L)
    H = build_operator(U)
    lam, v = solve_min_eigenpair(H)
    assert isinstance(lam, float)
    assert np.isfinite(lam)


def test_solve_min_eigenpair_eigenvector_normalized():
    U = make_U(L)
    H = build_operator(U)
    lam, v = solve_min_eigenpair(H)
    assert abs(np.linalg.norm(v) - 1.0) < 1e-10


def test_solve_min_eigenpair_sign_convention():
    U = make_U(L)
    H = build_operator(U)
    lam, v = solve_min_eigenpair(H)
    max_idx = np.argmax(np.abs(v))
    assert v[max_idx] > 0 or abs(v[max_idx]) < 1e-14  # max abs is positive


def test_compute_width_uniform():
    # uniform |v|^2 -> width = std of positions
    M = 10
    v = np.ones(M) / np.sqrt(M)
    k0 = float(np.argmax(np.abs(v)))  # any position (all equal)
    # Expected: sqrt(mean((k-k0)^2)) for k in 0..M-1
    k = np.arange(M, dtype=float)
    expected = np.sqrt(np.trapz(v**2 * (k - k0)**2) / np.trapz(v**2))
    w = compute_width(v)
    assert abs(w - expected) < 1e-10


def test_compute_width_delta():
    # delta at position 5 -> width = 0
    M = 10
    v = np.zeros(M)
    v[5] = 1.0
    w = compute_width(v)
    assert w < 1e-10


def test_compute_localization_distance_end():
    # v peaked at last element of interior array -> distance should be 0
    window_L = 10  # interior size = 8
    M = window_L - 2
    v = np.zeros(M)
    v[-1] = 1.0  # peak at interior end
    d = compute_localization_distance(v, window_L)
    assert d == 0.0


def test_compute_localization_distance_start():
    # v peaked at first element -> distance = L-3
    window_L = 10
    M = window_L - 2
    v = np.zeros(M)
    v[0] = 1.0  # peak at start
    d = compute_localization_distance(v, window_L)
    assert d == float(window_L - 3)


def test_compute_potential_moments_returns_two_floats():
    U = np.random.RandomState(42).normal(0, 1, 80)
    sk, kurt = compute_potential_moments(U)
    assert isinstance(sk, float)
    assert isinstance(kurt, float)


def test_rolling_analysis_output_length():
    np.random.seed(42)
    N = 50
    window_L = 10
    envelope = np.abs(np.sin(np.linspace(0, 10, N))) * 5 + 1
    dates = pd.date_range('2000-01-01', periods=N, freq='B')
    df = rolling_schrodinger_analysis(dates, envelope, window_L=window_L)
    expected = N - window_L + 1
    assert len(df) == expected


def test_rolling_analysis_columns():
    np.random.seed(0)
    N = 30
    window_L = 10
    envelope = np.abs(np.random.randn(N)) + 1
    dates = pd.date_range('2000-01-01', periods=N, freq='B')
    df = rolling_schrodinger_analysis(dates, envelope, window_L=window_L)
    required = {'date', 'lambda_min', 'abs_lambda_min', 'width', 'loc_distance', 'skewness', 'kurtosis'}
    assert required.issubset(df.columns)
