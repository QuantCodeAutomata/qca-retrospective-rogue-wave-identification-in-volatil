import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pytest
from scipy.integrate import trapezoid
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
    expected = np.sqrt(trapezoid(v**2 * (k - k0)**2) / trapezoid(v**2))
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
    # Last interior sample is one step from the observed window endpoint
    window_L = 10  # interior size = 8
    M = window_L - 2
    v = np.zeros(M)
    v[-1] = 1.0  # peak at interior end
    d = compute_localization_distance(v, window_L)
    assert d == 1.0


def test_compute_localization_distance_start():
    # First interior sample is index 1; window end is index L-1
    window_L = 10
    M = window_L - 2
    v = np.zeros(M)
    v[0] = 1.0  # peak at start
    d = compute_localization_distance(v, window_L)
    assert d == float(window_L - 2)


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


@pytest.mark.parametrize('delta_t', [0.5, 1.0, 2.0])
def test_constant_potential_eigenpair_matches_closed_form(delta_t):
    length = 12
    amplitude_squared = 100.0
    h = build_operator(np.full(length, -amplitude_squared), delta_t=delta_t)
    lam, v = solve_min_eigenpair(h)
    m = length-2
    expected = -amplitude_squared + (1-np.cos(np.pi/(m+1)))/delta_t**2
    assert lam == pytest.approx(expected, abs=1e-11)
    np.testing.assert_allclose(h @ v, lam*v, atol=1e-11)
    exact_vector = np.sin(np.arange(1, m+1)*np.pi/(m+1))
    exact_vector /= np.linalg.norm(exact_vector)
    np.testing.assert_allclose(v, exact_vector, atol=1e-10)


def test_kinetic_bound_explains_rolling_max_baseline():
    rng = np.random.default_rng(317)
    for _ in range(10):
        envelope = rng.uniform(10, 40, 80)
        a = max(envelope[1:-1]**2)
        lam, _ = solve_min_eigenpair(build_operator(-envelope**2))
        assert a-1-1e-9 <= abs(lam) <= a+1e-9


def test_boundary_convention_controls_retained_endpoints():
    u = np.zeros(10)
    u[-1] = -1000
    lam_interior, _ = solve_min_eigenpair(build_operator(u))
    lam_ghost, _ = solve_min_eigenpair(build_operator(u, 'dirichlet_ghost'))
    assert lam_interior > 0  # observed endpoints are fixed zeros
    assert lam_ghost < -999
    assert build_operator(u, 'dirichlet_ghost').shape == (10, 10)


def test_unknown_boundary_condition_rejected():
    with pytest.raises(ValueError, match='boundary_condition'):
        build_operator(np.zeros(10), boundary_condition='unsupported')


@pytest.mark.parametrize('delta_t', [0, -1, np.nan, np.inf])
def test_bad_time_spacing_rejected(delta_t):
    with pytest.raises(ValueError, match='delta_t'):
        build_operator(np.zeros(10), delta_t=delta_t)


def test_complex_width_uses_magnitude_and_time_units():
    # |v|²=[1,4,1]; trapezoid denominator=5 and numerator=1.
    v = np.array([1j, 2j, 1j])
    assert compute_width(v) == pytest.approx(np.sqrt(1/5))
    assert compute_width(v, delta_t=2) == pytest.approx(2*np.sqrt(1/5))


def test_rolling_width_includes_known_dirichlet_endpoints():
    # L=4, equal interior components; padded density is [0, .5, .5, 0].
    dates = pd.date_range('2000-01-01', periods=4)
    result = rolling_schrodinger_analysis(dates, np.ones(4), window_L=4)
    assert result.loc[0, 'width'] == pytest.approx(np.sqrt(0.5))
    assert result.loc[0, 'loc_distance'] in (1., 2.)


def test_full_vector_distance_at_actual_window_end():
    v = np.zeros(10)
    v[-1] = 1
    assert compute_localization_distance(v, 10) == 0.0


def test_short_rolling_output_preserves_schema():
    dates = pd.date_range('2000-01-01', periods=2)
    df = rolling_schrodinger_analysis(dates, np.ones(2), window_L=10)
    assert df.empty
    assert 'lambda_min' in df and 'date' in df


def test_rolling_does_not_suppress_invalid_input():
    dates = pd.date_range('2000-01-01', periods=10)
    with pytest.raises(ValueError):
        rolling_schrodinger_analysis(dates, np.full(10, np.nan), window_L=4)
    with pytest.raises(ValueError):
        rolling_schrodinger_analysis(dates, np.ones(9), window_L=4)
