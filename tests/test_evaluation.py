"""Regression tests for the paper's categories and exact trading-day windows."""
import numpy as np
import pandas as pd
import pytest
from src.evaluation import collapse_signal_runs, classify_first_signals, compute_detection_metrics


def peaks(calendar, specs):
    return pd.DataFrame([{'date': calendar[i], 'severity': severity}
                         for i, severity in specs], columns=['date', 'severity'])


def classify(calendar, signal_positions, specs, **kwargs):
    return classify_first_signals(calendar[signal_positions], peaks(calendar, specs),
                                  trading_dates=calendar, **kwargs)


def test_signal_runs_strict_threshold_and_empty():
    dates = pd.bdate_range('2020-01-01', periods=8)
    values = pd.Series([300, 301, 400, 300, 301, 301, 0, 500], index=dates)
    assert collapse_signal_runs(values, 300).equals(dates[[1, 4, 7]])
    assert len(collapse_signal_runs(values.iloc[:0], 300)) == 0


def test_missing_warning_does_not_create_false_episode():
    dates = pd.bdate_range('2020-01-01', periods=3)
    with pytest.raises(ValueError, match='finite'):
        collapse_signal_runs(pd.Series([301, np.nan, 301], index=dates), 300)


def test_windows_use_observed_calendar_not_weekday_or_calendar_approximation():
    # Long calendar interruption: still precisely 240 observed sessions to peak.
    dates = pd.bdate_range('2020-01-01', periods=500).delete(np.arange(80, 180))
    result = classify(dates, [9, 10, 11], [(250, 'major')])
    assert list(result.classification) == ['false', 'detected', 'detected']
    assert list(result.lead_trading_days.iloc[1:]) == [240, 239]


def test_post_peak_late_and_recovery_boundaries():
    dates = pd.bdate_range('2020-01-01', periods=500)
    result = classify(dates, [100, 110, 111, 180, 181],
                      [(100, 'major'), (300, 'major')])
    assert list(result.classification) == ['late', 'late', 'recovery', 'recovery', 'detected']
    assert result.associated_peak_date.iloc[0] == dates[100]
    assert result.associated_peak_date.iloc[-1] == dates[300]


def test_major_within_horizon_is_not_intercepted_by_nearer_lower_peak():
    # Paper supplementary Table2: 1997 alerts have a lower peak first, then
    # a major peak within 240 days; they still count as useful for major.
    dates = pd.bdate_range('2020-01-01', periods=400)
    result = classify(dates, [20], [(30, 'lower'), (254, 'major')])
    assert result.classification.iloc[0] == 'detected'
    assert result.associated_peak_date.iloc[0] == dates[254]


def test_low_is_not_false_and_same_day_low_is_late_only_for_lower_score():
    dates = pd.bdate_range('2020-01-01', periods=500)
    specs = [(200, 'lower'), (450, 'major')]
    major = classify(dates, [190, 200], specs, severity='major')
    lower = classify(dates, [190, 200], specs, severity='lower')
    assert list(major.classification) == ['low', 'low']
    assert list(lower.classification) == ['detected', 'late']
    assert compute_detection_metrics(major, peaks(dates, specs))['false_signal_pct'] == 0
    assert compute_detection_metrics(lower, peaks(dates, specs), 'lower')['false_signal_pct'] == 0


def test_censored_tail_is_optional_and_reported():
    dates = pd.bdate_range('2020-01-01', periods=400)
    specs = [(50, 'major')]
    finite = classify(dates, [100, 300], specs)
    censored = classify(dates, [100, 300], specs, censor_unresolved=True)
    assert list(finite.classification) == ['false', 'false']
    assert list(censored.classification) == ['false', 'censored']
    metrics = compute_detection_metrics(censored, peaks(dates, specs))
    assert metrics['n_signals'] == 2
    assert metrics['n_evaluated_signals'] == 1
    assert metrics['n_censored'] == 1
    assert metrics['false_signal_pct'] == 100


def test_no_peaks_preserves_false_signals_and_undefined_recall():
    dates = pd.bdate_range('2020-01-01', periods=400)
    result = classify(dates, [0, 300], [])
    metrics = compute_detection_metrics(result, peaks(dates, []))
    assert metrics['n_signals'] == metrics['n_false'] == 2
    assert metrics['false_signal_pct'] == 100
    assert metrics['peaks_detected_pct'] is None
    assert metrics['precision_pct'] == 0


def test_no_signals_does_not_claim_zero_precision():
    dates = pd.bdate_range('2020-01-01', periods=400)
    p = peaks(dates, [(100, 'major')])
    result = classify(dates, [], [(100, 'major')])
    metrics = compute_detection_metrics(result, p)
    assert metrics['peaks_detected_pct'] == 0
    assert metrics['precision_pct'] is None
    assert metrics['false_signal_pct'] is None


def test_precision_excludes_late_and_recall_counts_unique_peaks():
    dates = pd.bdate_range('2020-01-01', periods=600)
    p = peaks(dates, [(300, 'major'), (550, 'major')])
    result = classify(dates, [100, 200, 300, 311], [(300, 'major'), (550, 'major')])
    metrics = compute_detection_metrics(result, p)
    assert metrics['n_detected'] == 2  # warning episodes
    assert metrics['n_unique_detected_peaks'] == 1  # actual events
    assert metrics['n_late'] == 1
    assert metrics['n_recovery'] == 1
    assert metrics['peaks_detected_pct'] == 50
    assert metrics['precision_pct'] == 50
    assert metrics['precision_excl_late_pct'] == pytest.approx(200 / 3)


def test_oos_boundary_retains_old_peak_context_without_earning_old_signal_recall():
    dates = pd.bdate_range('2020-01-01', periods=500)
    specs = [(100, 'major'), (350, 'major')]
    # Date105 is late relative to a PRE-OOS peak; date300 predicts OOS peak.
    result = classify(dates, [90, 105, 300], specs)
    metrics = compute_detection_metrics(result, peaks(dates, specs),
                                        evaluation_start=dates[101])
    assert metrics['n_signals'] == 2
    assert metrics['n_late'] == 1
    assert metrics['n_peaks'] == 1
    assert metrics['n_unique_detected_peaks'] == 1
    assert metrics['precision_pct'] == 50


def test_oos_does_not_reset_running_signal_episode():
    dates = pd.bdate_range('2020-01-01', periods=400)
    W = pd.Series(0., index=dates)
    W.iloc[90:110] = 400
    first = collapse_signal_runs(W, 300)
    p = peaks(dates, [(200, 'major')])
    result = classify_first_signals(first, p, trading_dates=dates)
    metrics = compute_detection_metrics(result, p, evaluation_start=dates[100])
    assert metrics['n_signals'] == 0
    assert metrics['n_unique_detected_peaks'] == 0


def test_explicit_evaluation_end_censors_future_event_credit():
    dates = pd.bdate_range('2020-01-01', periods=400)
    p = peaks(dates, [(350, 'major')])
    result = classify(dates, [300], [(350, 'major')], observation_end=dates[320])
    metrics = compute_detection_metrics(result, p, evaluation_end=dates[320])
    assert metrics['n_censored'] == 1
    assert metrics['n_detected'] == 0
    assert metrics['precision_pct'] is None


def test_metric_aggregation_never_reclassifies_a_full_history_ledger():
    dates = pd.bdate_range('2020-01-01', periods=400)
    p = peaks(dates, [(350, 'major')])
    result = classify(dates, [300], [(350, 'major')])
    original = result.copy(deep=True)
    with pytest.raises(ValueError, match='observation_end'):
        compute_detection_metrics(result, p, evaluation_end=dates[320])
    pd.testing.assert_frame_equal(result, original)


def test_observation_cutoff_censors_unresolved_false_and_ignores_future_signals():
    dates = pd.bdate_range('2020-01-01', periods=600)
    full = classify(dates, [100, 450], [])
    assert list(full.classification) == ['false', 'false']
    asof = classify(dates, [100, 450], [], observation_end=dates[120])
    assert list(asof.signal_date) == [dates[100]]
    assert list(asof.classification) == ['censored']
    assert pd.isna(asof.associated_peak_date.iloc[0])


def test_unscoped_false_ledger_cannot_be_silently_scored_at_an_immature_end():
    # Full history establishes false, but only 20/240 observations were known
    # at the requested cutoff; no future association exists to flag leakage.
    dates = pd.bdate_range('2020-01-01', periods=600)
    p = peaks(dates, [])
    full = classify(dates, [100], [])
    assert full.classification.iloc[0] == 'false'
    assert pd.isna(full.associated_peak_date.iloc[0])
    with pytest.raises(ValueError, match='matching observation_end'):
        compute_detection_metrics(full, p, evaluation_end=dates[120])
    asof = classify(dates, [100], [], observation_end=dates[120])
    result = compute_detection_metrics(asof, p, evaluation_end=dates[120])
    assert result['n_censored'] == 1
    assert result['n_false'] == 0
    assert result['precision_pct'] is None


def test_end_date_requires_matching_cutoff_metadata_after_copy_or_reload():
    dates = pd.bdate_range('2020-01-01', periods=600)
    p = peaks(dates, [])
    asof = classify(dates, [100], [], observation_end=dates[120])
    assert compute_detection_metrics(asof.copy(), p, evaluation_end=dates[120])['n_censored'] == 1
    with pytest.raises(ValueError, match='matching observation_end'):
        compute_detection_metrics(asof, p, evaluation_end=dates[121])
    reloaded = asof.copy()
    reloaded.attrs.clear()
    with pytest.raises(ValueError, match='require reclassification'):
        compute_detection_metrics(reloaded, p, evaluation_end=dates[120])


def test_observation_cutoff_uses_observed_horizon_and_exact_maturity_boundary():
    dates = pd.bdate_range('2020-01-01', periods=700).delete(np.arange(110, 210))
    immature = classify(dates, [100], [], observation_end=dates[339])
    mature = classify(dates, [100], [], observation_end=dates[340])
    assert immature.classification.iloc[0] == 'censored'
    assert mature.classification.iloc[0] == 'false'


def test_observation_cutoff_with_lower_event_keeps_major_horizon_pending():
    dates = pd.bdate_range('2020-01-01', periods=600)
    specs = [(110, 'lower'), (350, 'major')]
    major = classify(dates, [100], specs, observation_end=dates[120])
    lower = classify(dates, [100], specs, severity='lower', observation_end=dates[120])
    assert major.classification.iloc[0] == 'censored'
    assert major.associated_peak_date.iloc[0] == dates[110]
    assert lower.classification.iloc[0] == 'detected'


def test_observation_cutoff_retains_previous_peak_context_and_between_session_end():
    dates = pd.bdate_range('2020-01-01', periods=500)
    specs = [(100, 'major'), (350, 'major')]
    result = classify(dates, [105, 300], specs,
                      observation_end=dates[320] + pd.Timedelta(hours=12))
    assert list(result.classification) == ['late', 'censored']
    metrics = compute_detection_metrics(result, peaks(dates, specs),
                                        evaluation_start=dates[101], evaluation_end=dates[320])
    assert metrics['n_late'] == 1
    assert metrics['n_censored'] == 1
    assert metrics['n_peaks'] == 0


def test_paper_table1_denominators_from_published_event_ledger():
    # Dates transcribed from supplied Supplementary Table1 (p17). The weekday
    # calendar here is synthetic; it tests category/count algebra, not daily data.
    major = ['1997-10-28', '1998-09-02', '2001-09-19', '2002-10-07',
             '2008-10-14', '2010-05-20', '2011-08-09', '2015-08-26',
             '2018-02-06', '2020-03-16', '2022-10-04', '2025-04-08']
    lower = ['1991-01-14', '2018-12-26', '2024-08-05']
    signals = ['1997-10-30', '2001-09-17', '2002-07-24', '2008-09-18',
               '2008-09-24', '2008-10-02', '2010-05-10', '2010-05-13',
               '2010-05-19', '2011-08-08', '2015-08-25', '2018-02-06',
               '2020-02-28', '2021-12-06', '2022-01-27', '2022-02-01',
               '2024-08-05', '2025-03-11', '2025-04-07']
    calendar = pd.bdate_range('1990-01-01', '2025-05-01')
    p = pd.DataFrame({'date': pd.to_datetime(major + lower),
                      'severity': ['major'] * len(major) + ['lower'] * len(lower)})
    for severity, recall, late, precision_ex_late in [('major', 75, 2, 1600/17),
                                                     ('lower', 60, 3, 100)]:
        cls = classify_first_signals(pd.DatetimeIndex(signals), p, severity,
                                     trading_dates=calendar)
        m = compute_detection_metrics(cls, p, severity)
        assert m['n_signals'] == 19
        assert m['n_unique_detected_peaks'] == 9
        assert m['n_detected'] == 16
        assert m['n_late'] == late
        assert m['peaks_detected_pct'] == recall
        assert m['false_signal_pct'] == 0
        assert m['precision_pct'] == pytest.approx(1600/19)
        assert m['precision_excl_late_pct'] == pytest.approx(precision_ex_late)


def test_calendar_is_mandatory_and_invalid_dates_rejected():
    dates = pd.bdate_range('2020-01-01', periods=100)
    with pytest.raises(TypeError):
        classify_first_signals(dates[[10]], peaks(dates, [(50, 'major')]))
    with pytest.raises(ValueError, match='trading_dates'):
        classify_first_signals(pd.DatetimeIndex(['2020-01-04']),
                               peaks(dates, [(50, 'major')]), trading_dates=dates)


def test_known_lower_event_does_not_mature_a_pending_major_horizon():
    dates = pd.bdate_range('2020-01-01', periods=400)
    specs = [(350, 'lower')]
    result = classify(dates, [300], specs, censor_unresolved=True)
    assert result.classification.iloc[0] == 'censored'
    lower = classify(dates, [300], specs, severity='lower', censor_unresolved=True)
    assert lower.classification.iloc[0] == 'detected'
