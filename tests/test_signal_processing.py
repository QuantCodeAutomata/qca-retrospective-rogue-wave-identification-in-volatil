import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pytest
from src.signal_processing import (
    mirror_series, spectral_peak_filter, reconstruct_filtered_signal,
    extract_envelope, process_series
)


def make_sine(N=100, freq=0.05, amp=1.0, offset=10.0):
    t = np.arange(N)
    return offset + amp * np.sin(2 * np.pi * freq * t)


def test_mirror_series_length():
    x = np.arange(10, dtype=float)
    mirrored, N = mirror_series(x)
    assert len(mirrored) == 2 * N - 2
    assert N == 10


def test_mirror_series_symmetry():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    mirrored, N = mirror_series(x)
    # Should be [1,2,3,4,5,4,3,2] length 8
    assert len(mirrored) == 8
    np.testing.assert_array_equal(mirrored[:5], x)
    np.testing.assert_array_equal(mirrored[5:], [4.0, 3.0, 2.0])


def test_mirror_series_no_duplicate_endpoint():
    x = np.array([10.0, 20.0, 30.0])
    mirrored, N = mirror_series(x)
    # [10, 20, 30, 20] - no duplicate 10 at the end or 30 duplicated at junction
    assert mirrored[N-1] == x[-1]  # junction
    assert mirrored[N] == x[-2]    # reflection starts from x[N-2]


def test_spectral_peak_filter_returns_complex():
    x = make_sine()
    mirrored, _ = mirror_series(x)
    X_filtered = spectral_peak_filter(mirrored)
    assert np.iscomplexobj(X_filtered)


def test_spectral_peak_filter_shape():
    x = make_sine(N=64)
    mirrored, _ = mirror_series(x)
    X_filtered = spectral_peak_filter(mirrored)
    expected_len = len(mirrored) // 2 + 1
    assert len(X_filtered) == expected_len


def test_reconstruct_filtered_signal_length():
    x = make_sine(N=50)
    mirrored, N = mirror_series(x)
    X_filtered = spectral_peak_filter(mirrored)
    reconstructed = reconstruct_filtered_signal(X_filtered, n=N)
    assert len(reconstructed) == N


def test_extract_envelope_nonnegative():
    x = make_sine(N=100)
    env = extract_envelope(x)
    assert np.all(env >= 0)


def test_extract_envelope_length():
    x = make_sine(N=80)
    env = extract_envelope(x)
    assert len(env) == len(x)


def test_process_series_length():
    x = make_sine(N=120)
    env = process_series(x)
    assert len(env) == len(x)


def test_process_series_nonnegative():
    x = make_sine(N=120)
    env = process_series(x)
    assert np.all(env >= 0)


def test_process_series_with_sine():
    # Pure sine wave: envelope should be roughly constant
    N = 200
    t = np.arange(N)
    x = 10 + 5 * np.sin(2 * np.pi * 0.05 * t)
    env = process_series(x, percentile_threshold=50.0)  # low threshold to keep signal
    assert len(env) == N
    assert np.all(env >= 0)


def test_process_series_single_element_edge():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    env = process_series(x)
    assert len(env) == 4
    assert np.all(env >= 0)


@pytest.mark.parametrize('percentile', [92.5, 95.0])
def test_spectral_peak_filter_various_percentiles(percentile):
    x = make_sine(N=128)
    mirrored, _ = mirror_series(x)
    X_filtered = spectral_peak_filter(mirrored, percentile_threshold=percentile)
    assert np.iscomplexobj(X_filtered)
    assert len(X_filtered) == len(mirrored) // 2 + 1


def test_spectral_peak_filter_percentile_92():
    x = make_sine(N=64)
    mirrored, _ = mirror_series(x)
    X_92 = spectral_peak_filter(mirrored, 92.5)
    assert X_92 is not None


def test_spectral_peak_filter_percentile_95():
    x = make_sine(N=64)
    mirrored, _ = mirror_series(x)
    X_95 = spectral_peak_filter(mirrored, 95.0)
    assert X_95 is not None
