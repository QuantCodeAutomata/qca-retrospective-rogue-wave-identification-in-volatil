import numpy as np
import pandas as pd
import pytest
from src.diagnostics import (compute_gradient_series, compute_envelope_gradient,
                             assign_days_to_next_peak, bin_by_days_to_peak)


def test_exact_peak_day_and_unknown_tail_not_far_future():
    dates = pd.bdate_range('2020-01-01', periods=50).delete([10, 11, 12])
    d = assign_days_to_next_peak(dates, dates[[6, 40]])
    assert d.iloc[1] == 5
    assert d.iloc[6] == 0
    assert d.iloc[7] == 33
    assert d.iloc[40] == 0
    assert np.isnan(d.iloc[41])
    bins = bin_by_days_to_peak(d)
    assert bins.iloc[1] == '0-5'
    assert bins.iloc[7] == '>30'
    assert pd.isna(bins.iloc[6])
    assert pd.isna(bins.iloc[41])


def test_no_peaks_gives_no_diagnostic_groups():
    dates = pd.bdate_range('2020-01-01', periods=10)
    d = assign_days_to_next_peak(dates, pd.DatetimeIndex([]))
    assert d.isna().all()
    assert bin_by_days_to_peak(d).isna().all()


def test_gradient_empty_singleton_and_correct_centered_values():
    for n in [0, 1]:
        s = pd.Series(np.arange(n, dtype=float))
        result = compute_gradient_series(s)
        assert len(result) == n
        assert result.isna().all()
    s = pd.Series([0., 1., 4., 9.])
    np.testing.assert_array_equal(compute_gradient_series(s), [1., 2., 4., 5.])


def test_squared_envelope_gradient_alignment():
    dates = pd.bdate_range('2020-01-01', periods=5)
    result = compute_envelope_gradient(np.arange(5), dates, window_L=3)
    assert result.index.equals(dates[2:])
    np.testing.assert_array_equal(result, [5, 6, 7])


def test_peak_date_must_be_on_calendar():
    dates = pd.bdate_range('2020-01-01', periods=10)
    with pytest.raises(ValueError):
        assign_days_to_next_peak(dates, pd.DatetimeIndex(['2020-01-04']))
