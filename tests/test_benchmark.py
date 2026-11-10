"""Controls test calendar coverage and event/episode denominators independently."""
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from src.benchmark import CATALOG_DIRECTORY, evaluate_catalog, load_paper_catalog
from src.evaluation import classify_first_signals, collapse_signal_runs, compute_detection_metrics


CONFIG = {'threshold_warning': 300., 'detection_window_days': 240,
          'min_inter_peak_days': 80, 'late_signal_days': 10, 'insample_end': None}


def sample():
    dates = pd.bdate_range('2020-01-01', periods=600).delete([21, 22, 23])
    values = np.zeros(len(dates) - 88)
    for start, stop in [(100, 103), (150, 151), (300, 301), (590, len(dates))]:
        values[start - 88:stop - 88] = 400.
    warnings = pd.DataFrame({'date': dates[88:], 'W_i': values})
    peaks = pd.DataFrame({'date': dates[[200, 300, 400]], 'severity': ['major', 'major', 'lower']})
    return dates, warnings, peaks


@pytest.mark.parametrize('index,major,total', [('VIX', 12, 15), ('VXO', 8, 13), ('VSTOXX', 8, 9)])
def test_paper_catalog_is_hashed_and_exposes_complete_coverage(index, major, total):
    # Weekday-only dates test the source catalog API, not market performance.
    calendar = pd.bdate_range('1986-01-01', '2026-01-01')
    peaks, metadata = load_paper_catalog(index, calendar)
    assert len(peaks) == total
    assert peaks.severity.eq('major').sum() == major
    assert metadata['covered_events'] == metadata['total_events'] == total
    assert metadata['coverage_complete'] is True
    assert metadata['out_of_range_events'] == []
    path = CATALOG_DIRECTORY / f'paper_{index}_supplement_table.csv'
    assert metadata['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    json.dumps(metadata, allow_nan=False)


def test_paper_catalog_partial_coverage_is_recorded_without_fabricated_dates():
    calendar = pd.bdate_range('2020-01-01', '2020-12-31')
    peaks, metadata = load_paper_catalog('VIX', calendar)
    assert list(peaks.date) == [pd.Timestamp('2020-03-16')]
    assert metadata['coverage_complete'] is False
    assert metadata['covered_events'] == 1
    assert len(metadata['out_of_range_events']) == metadata['total_events'] - 1
    without_peak = calendar[calendar != pd.Timestamp('2020-03-16')]
    with pytest.raises(ValueError, match='2020-03-16'):
        load_paper_catalog('VIX', without_peak)


def test_empty_calendar_is_explicit_no_coverage():
    peaks, metadata = load_paper_catalog('VIX', pd.DatetimeIndex([]))
    assert peaks.empty
    assert metadata['covered_events'] == 0
    assert metadata['coverage_complete'] is False
    assert metadata['calendar_start'] is None


def test_benchmark_preserves_full_sample_counts_and_separates_episodes_from_events():
    dates, warnings, peaks = sample()
    result = evaluate_catalog(warnings, peaks, dates, CONFIG)
    first = collapse_signal_runs(pd.Series(warnings.W_i.to_numpy(), index=warnings.date), 300)
    for severity in ('major', 'lower'):
        cls = classify_first_signals(first, peaks, severity=severity, trading_dates=dates)
        assert result['metrics']['full_sample'][severity] == compute_detection_metrics(cls, peaks, severity)
    events = result['events']['major']
    assert len(events) == 2
    assert list(events.detected) == [True, False]
    assert list(events.n_useful_episodes) == [2, 0]
    assert events.first_signal_date.iloc[0] == dates[100]
    assert events.lead_trading_days.iloc[0] == 100
    assert pd.isna(events.first_signal_date.iloc[1])
    assert result['metrics']['full_sample']['major']['n_unique_detected_peaks'] == 1
    assert result['metrics']['full_sample']['major']['n_detected'] == 2
    assert result['metrics']['endpoint_censored']['major']['n_censored'] == 1
    assert set(result['horizons'].horizon_observations) == {20, 60, 120, 240}
    assert len(result['horizons']) == 8
    json.dumps(result['metrics'], allow_nan=False)
    json.dumps(result['diagnostics'], allow_nan=False)


def test_episode_durations_alarm_fraction_and_leads_use_observations():
    dates, warnings, peaks = sample()
    result = evaluate_catalog(warnings, peaks, dates, CONFIG)
    episodes = result['episodes']
    assert list(episodes.duration_observations) == [3, 1, 1, 7]
    assert list(episodes.open_at_end) == [False, False, False, True]
    assert result['diagnostics']['days_above_threshold'] == 12
    assert result['diagnostics']['alarm_fraction'] == pytest.approx(12 / len(warnings))
    assert result['diagnostics']['useful_episode_lead_observations']['major'] == {
        'count': 2, 'min': 50., 'median': 75., 'max': 100.}
    assert result['diagnostics']['detected_event_first_lead_observations']['major']['count'] == 1


def test_benchmark_oos_preserves_context_and_does_not_restart_episode():
    dates, warnings, peaks = sample()
    config = {**CONFIG, 'insample_end': str(dates[101].date())}
    result = evaluate_catalog(warnings, peaks, dates, config)
    oos = result['metrics']['out_of_sample']
    assert oos['status'] == 'configured'
    assert oos['metrics']['major']['n_detected'] == 1
    assert oos['metrics']['major']['n_signals'] == 3
    assert dates[102] not in set(result['episodes'].signal_date)


def test_benchmark_rejects_missing_warning_rows_and_unknown_catalog_labels():
    dates, warnings, peaks = sample()
    with pytest.raises(ValueError, match='consecutive'):
        evaluate_catalog(warnings.drop(index=20), peaks, dates, CONFIG)
    with pytest.raises(ValueError, match='severity'):
        evaluate_catalog(warnings, peaks.assign(severity='typo'), dates, CONFIG)
    with pytest.raises(ValueError, match='finite'):
        evaluate_catalog(warnings.assign(W_i=np.nan), peaks, dates, CONFIG)


def test_empty_warning_ledger_keeps_undefined_ratios_json_safe():
    dates, warnings, peaks = sample()
    result = evaluate_catalog(warnings.iloc[:0], peaks, dates, CONFIG)
    assert result['episodes'].empty
    assert result['metrics']['full_sample']['major']['precision_pct'] is None
    assert result['metrics']['after_warmup']['major']['n_peaks'] == 0
    assert result['diagnostics']['alarm_fraction'] is None
    json.dumps(result['diagnostics'], allow_nan=False)
