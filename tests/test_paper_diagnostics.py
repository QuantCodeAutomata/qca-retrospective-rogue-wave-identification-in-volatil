import json

import numpy as np
import pandas as pd
import pytest

from src.paper_diagnostics import (
    aftershock_window,
    envelope_increment_diagnostics,
    fit_omori_counts,
    lagged_gradient_correlation,
    log_index_decay,
    omori_integral,
    run_paper_diagnostics,
)


def warning_ledger(dates, gradients, event_dates=None):
    return pd.DataFrame({"date": dates, "M_i": gradients, "C_i": np.ones(len(dates), dtype=int),
                         "W_i": gradients,
                         "event_date": dates if event_dates is None else event_dates})


def test_correlation_positive_lag_is_future_high_on_full_calendar():
    rng = np.random.default_rng(1234)
    # Irregular calendar: neither business-day offsets nor selected-signal-row
    # offsets may replace positions in this input.
    dates = pd.bdate_range("2020-01-01", periods=90).delete([6, 17, 28])
    highs = pd.Series(rng.uniform(10, 90, len(dates)), index=dates)
    source = np.arange(0, len(dates) - 4, 2)
    gradients = highs.iloc[source + 4].to_numpy()
    gradients[::5] = 0.0  # cutoff must not compress the observed-session calendar
    ledger = warning_ledger(dates[source], gradients)
    result = lagged_gradient_correlation(highs, ledger, range(-6, 7))
    best = result.loc[result.pearson_r.idxmax()]
    assert best.lag_observations == 4
    assert best.pearson_r == pytest.approx(1.0)
    assert best.n_pairs == np.count_nonzero(gradients > 1e-4)
    row = result.loc[result.lag_observations == -6].iloc[0]
    assert row.n_pairs == np.count_nonzero((source >= 6) & (gradients > 1e-4))


def test_correlation_cutoff_constant_and_insufficient_pairs():
    dates = pd.bdate_range("2020-01-01", periods=4)
    highs = pd.Series([1., 2., 3., 4.], index=dates)
    ledger = warning_ledger(dates, [0.0, 1e-4, 2.0, 2.0])
    result = lagged_gradient_correlation(highs, ledger, [0, 1, 2])
    assert result.n_pairs.tolist() == [2, 1, 0]
    assert result.status.tolist() == ["constant_input", "insufficient_pairs", "insufficient_pairs"]
    assert result.pearson_r.isna().all()


def test_omori_integral_special_cases_and_continuity():
    t = np.array([0., 1., 4., 20.])
    np.testing.assert_allclose(omori_integral(t, 2, 0), t)
    np.testing.assert_allclose(omori_integral(t, 2, 1), np.log1p(t / 2))
    np.testing.assert_allclose(omori_integral(t, 2, 2), 1 / 2 - 1 / (t + 2))
    np.testing.assert_allclose(omori_integral(t, 2, 1 + 1e-10), np.log1p(t / 2))
    with pytest.raises(ValueError):
        omori_integral(t, 0, 1)


def test_omori_no_events_and_insufficient_events_are_not_zero_fits():
    empty = fit_omori_counts(np.zeros(11))
    assert empty["status"] == "no_events" and empty["K"] is None
    few = fit_omori_counts(np.array([0, 0, 1, 1, 2, 2]))
    assert few["status"] == "insufficient_events" and few["starts_attempted"] == 0
    with pytest.raises(ValueError):
        fit_omori_counts([0, 1, 0])


def test_omori_fit_runs_nine_starts_and_reports_constraints():
    # Exactly linear cumulative counts are the p=0 nested special case, so
    # the expected curve is known independently of the numerical optimizer.
    counts = np.arange(31)
    fit = fit_omori_counts(counts)
    assert fit["starts_attempted"] == 9
    assert fit["starts_converged"] > 0
    assert 0 <= fit["p"] <= 3 and 0.1 <= fit["c"] <= 30
    assert fit["K"] >= 0
    assert fit["r_squared"] > 0.999999
    np.testing.assert_allclose(fit["K"] * omori_integral(np.arange(31), fit["c"], fit["p"]),
                               counts, atol=5e-4)


def test_omori_optimizer_failure_is_explicit(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("forced solver failure")
    monkeypatch.setattr("src.paper_diagnostics.least_squares", fail)
    result = fit_omori_counts([0, 1, 2, 3, 3])
    assert result["status"] == "optimizer_failed"
    assert result["starts_attempted"] == 9 and result["starts_converged"] == 0
    assert result["K"] is None and len(result["failed_start_messages"]) == 9


def test_aftershock_anchor_exclusion_and_exact_horizon():
    dates = pd.bdate_range("2008-10-09", periods=9)
    highs = pd.Series(np.arange(9) + 20.0, index=dates)
    raw = pd.DataFrame({"date": [dates[2], dates[3], dates[6], dates[7]],
                        "exceeds_swh": [True, True, False, True]})
    window, status = aftershock_window(highs, raw, dates[2], 5)
    assert status["status"] == "completed"
    assert window.cumulative_count.tolist() == [0, 1, 1, 1, 1, 2]
    assert window.global_index_1based.tolist() == [3, 4, 5, 6, 7, 8]
    assert window.date.iloc[-1] == dates[7]
    assert aftershock_window(highs, raw, "2000-01-01", 5)[1]["reason"] == "anchor_absent"
    assert aftershock_window(highs, raw, dates[2], 7)[1]["reason"] == "insufficient_post_anchor_history"


def test_log_index_decay_uses_global_one_based_index_not_relative_time():
    positions = np.arange(101, 122)
    envelope = 3.0 * np.arange(1, 130, dtype=float) ** -0.75
    window = pd.DataFrame({"date": pd.bdate_range("2008-10-13", periods=len(positions)),
                           "global_index_1based": positions})
    data, fit = log_index_decay(envelope, window)
    assert fit["slope"] == pytest.approx(-0.75, abs=1e-12)
    assert fit["intercept"] == pytest.approx(np.log(3), abs=1e-12)
    assert fit["r_squared"] == pytest.approx(1)
    np.testing.assert_allclose(data.log_index, np.log(positions))
    envelope[100] = 0
    assert log_index_decay(envelope, window)[1]["status"] == "failed"


def test_s2_ddof_zero_shared_bins_counts_and_density():
    dates = pd.bdate_range("2000-01-03", periods=40)
    values = np.arange(40, dtype=float) ** 2 + 7
    increments, hist, meta = envelope_increment_diagnostics(dates, values)
    for lag in (1, 2, 5, 10, 20):
        group = increments.loc[increments.lag_observations == lag]
        expected = values[lag:] - values[:-lag]
        np.testing.assert_array_equal(group.increment, expected)
        assert group.standardized_increment.mean() == pytest.approx(0, abs=1e-12)
        assert group.standardized_increment.std(ddof=0) == pytest.approx(1)
    assert meta["standardization_ddof"] == 0
    for representation in ("raw", "standardized"):
        assert len(meta["shared_bin_edges"][representation]) == 101
        first_edges = None
        for lag, group in hist.loc[hist.representation == representation].groupby("lag_observations"):
            assert len(group) == 100 and group["count"].sum() == 40 - lag
            assert np.sum(group.probability_density * (group.bin_right - group.bin_left)) == pytest.approx(1)
            edges = np.r_[group.bin_left.to_numpy(), group.bin_right.iloc[-1]]
            if first_edges is None:
                first_edges = edges
            np.testing.assert_array_equal(edges, first_edges)


def test_s2_zero_variance_and_insufficient_history_are_explicit():
    dates = pd.bdate_range("2000-01-03", periods=3)
    increments, hist, meta = envelope_increment_diagnostics(dates, np.ones(3))
    assert increments.standardized_increment.isna().all()
    assert meta["lags"][0]["status"] == "zero_variance"
    assert meta["lags"][-1]["status"] == "insufficient_history"
    assert set(hist.representation) == {"raw"}


def test_entrypoint_writes_artifacts_and_preserves_repeated_event_dates(tmp_path):
    dates = pd.bdate_range("2020-01-02", periods=30)
    highs = pd.Series(20 + np.sin(np.arange(30)), index=dates)
    ledger = warning_ledger(dates[4:], np.arange(26) + 1.,
                            pd.DatetimeIndex([dates[3]] * 26))
    before = ledger.copy(deep=True)
    result = run_paper_diagnostics("VXO", highs, ledger,
                                   {"threshold_warning": 700}, tmp_path)
    pd.testing.assert_frame_equal(ledger, before)
    assert result["figures"]["S1"]["status"] == "not_applicable"
    assert result["figures"]["S3"]["status"] == "not_applicable"
    info = result["figures"]["S4"]["years"]["2020"]
    saved = pd.read_csv(tmp_path / info["table"])
    assert len(saved) == len(ledger) and saved.event_date.nunique() == 1
    assert (tmp_path / result["figures"]["S4"]["figure"]).stat().st_size > 0
    assert (tmp_path / result["figures"]["figure5"]["figure"]).stat().st_size > 0
    stored = json.loads((tmp_path / result["summary_path"]).read_text())
    assert stored == result


def test_entrypoint_vix_missing_anchors_and_no_warnings(tmp_path):
    dates = pd.bdate_range("2022-01-03", periods=30)
    highs = pd.Series(20 + np.sin(np.arange(30)), index=dates)
    result = run_paper_diagnostics("VIX", highs, None, {}, tmp_path,
                                   descriptive_envelope=highs.to_numpy())
    assert result["figures"]["S1"]["status"] == "unavailable"
    assert result["figures"]["S2"]["status"] == "completed"
    assert result["figures"]["figure5"]["status"] == "unavailable"
    assert result["figures"]["S3"]["status"] == "unavailable"
    assert result["figures"]["S4"]["status"] == "not_applicable"
    assert (tmp_path / result["figures"]["S2"]["figure"]).stat().st_size > 0


def test_warning_event_date_cannot_be_a_future_or_unobserved_date():
    dates = pd.bdate_range("2020-01-01", periods=5)
    highs = pd.Series(np.arange(5) + 1., index=dates)
    ledger = warning_ledger(dates[:3], [1, 2, 3], dates[1:4])
    with pytest.raises(ValueError, match="no later"):
        lagged_gradient_correlation(highs, ledger)
