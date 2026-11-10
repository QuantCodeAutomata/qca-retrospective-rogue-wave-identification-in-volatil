"""Control experiments must share timing and coordinates, not presumed outcomes."""
import numpy as np
import pandas as pd
import pytest

from src.realtime_pipeline import (
    WARNING_COLUMNS, compute_rolling_max_block, compute_warning_indicator,
    run_realtime_simulation,
)
from src.signal_processing import process_series


@pytest.mark.parametrize('boundary', ['dirichlet', 'dirichlet_ghost'])
@pytest.mark.parametrize('length,block', [(5, 3), (12, 7)])
def test_baseline_matches_independent_window_reference(boundary, length, block):
    values = np.array([9., 1., 2., 4., 1., 3., 7., 2., 3., 1., 6., 2., 9., 1., 8., 3., 4., 2., 5., 6.])
    actual = compute_rolling_max_block(values, block, length, boundary)
    expected = []
    for j in range(len(values)-block, len(values)):
        coords = range(j-length+2, j) if boundary == 'dirichlet' else range(j-length+1, j+1)
        expected.append(max(values[k]**2 for k in coords))
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize('boundary', ['dirichlet', 'dirichlet_ghost'])
def test_control_uses_same_prefix_and_preserves_primary_results(boundary, monkeypatch):
    import src.realtime_pipeline as pipeline
    values = 20 + 4*np.sin(np.arange(45)/3) + np.arange(45)/5
    series = pd.Series(values, index=pd.bdate_range('2020-01-01', periods=45))
    options = dict(window_L=12, block_len=7, boundary_condition=boundary,
                   threshold_grad_count=0.1, progress=False)
    primary = run_realtime_simulation(series, **options)
    calls = []
    original = pipeline.compute_envelope_at_day
    def counted(history, *args):
        calls.append(len(history))
        return original(history, *args)
    monkeypatch.setattr(pipeline, 'compute_envelope_at_day', counted)
    paired = run_realtime_simulation(series, baseline='rolling_max', **options)
    pd.testing.assert_frame_equal(primary, paired[WARNING_COLUMNS])
    assert calls == list(range(18, 46))  # exactly one envelope per available prefix
    for i, row in enumerate(paired.itertuples(), start=18):
        envelope = process_series(values[:i], 95, 'spectral_peaks')
        block = compute_rolling_max_block(envelope, 7, 12, boundary)
        m, c, w, offset = compute_warning_indicator(block, 0.1)
        assert (row.baseline_M_i, row.baseline_C_i, row.baseline_W_i) == (m, c, w)
        assert row.baseline_event_date == series.index[i-7+offset]
        assert row.baseline_event_date <= row.date
    # A threshold between unequal W values produces a valid disagreement.
    # Never encode universal equivalence as an acceptance criterion.
    diff = np.flatnonzero(np.abs(paired.W_i-paired.baseline_W_i) > 1e-8)
    assert len(diff)
    row = paired.iloc[diff[0]]
    threshold = (row.W_i + row.baseline_W_i)/2
    assert (row.W_i > threshold) != (row.baseline_W_i > threshold)


def test_baseline_causal_future_shock():
    series = pd.Series(20+np.sin(np.arange(40)), index=pd.bdate_range('2020-01-01', periods=40))
    kwargs = dict(window_L=8, block_len=3, baseline='rolling_max', progress=False)
    prefix = run_realtime_simulation(series.iloc[:30], **kwargs)
    series.iloc[30:] *= 20
    extended = run_realtime_simulation(series, **kwargs)
    pd.testing.assert_frame_equal(prefix, extended.iloc[:len(prefix)].reset_index(drop=True))


def test_descriptive_computation_shared_without_mutating_cached_results(tmp_path, monkeypatch):
    from run_experiments import run_project, demo_series
    import exp.common as common
    import src.schrodinger as schrodinger
    counts = {'envelope': 0, 'eigenanalysis': 0}
    original_env, original_diag = common.envelope_for, schrodinger.rolling_schrodinger_analysis
    def env(*args, **kwargs):
        counts['envelope'] += 1
        return original_env(*args, **kwargs)
    def diag(*args, **kwargs):
        counts['eigenanalysis'] += 1
        return original_diag(*args, **kwargs)
    monkeypatch.setattr(common, 'envelope_for', env)
    monkeypatch.setattr(schrodinger, 'rolling_schrodinger_analysis', diag)
    result = run_project('VIX', demo_series('VIX', n=120), experiments=[1,2,3], output_dir=tmp_path/'run')
    assert counts == {'envelope': 1, 'eigenanalysis': 1}
    assert 'days_to_next_peak' in result['results'][2]
    table = pd.read_csv(tmp_path/'run/exp1_VIX_raw_peaks.csv')
    assert 'raw_high' in table and 'severity' in table
    table3 = pd.read_csv(tmp_path/'run/exp3_VIX_gradient_data.csv')
    assert {'grad_lambda','grad_sq_env','raw_high','negative_potential','abs_lambda_min'} <= set(table3)


def test_paper_plot_catalog_and_standalone_synthetic_provenance(tmp_path, monkeypatch):
    import json
    from run_experiments import run_project, demo_series
    from data.data_loader import load_config
    import src.plotting as plotting
    series = demo_series('VIX', n=120)
    series.index = pd.bdate_range(end='2001-09-19', periods=120)
    cfg = load_config('VIX')
    cfg.update(labels='paper', baseline='rolling_max')
    captured = []
    def capture(raw, envelope, peaks, warnings, first, threshold, title, **kwargs):
        captured.append((peaks.copy(), title))
    monkeypatch.setattr(plotting, 'figure_warning_indicator', capture)
    output = tmp_path/'paper'
    run_project('VIX', series, cfg, experiments=[4], output_dir=output, progress=False)
    assert len(captured) == 1
    peaks, title = captured[0]
    assert peaks.date.tolist() == [pd.Timestamp('2001-09-19')]
    assert 'paper event catalog' in title and 'SYNTHETIC TEST' in title
    for filename in ['exp4_vix_evaluation.json',
                     'exp4_vix_baseline_rolling_max_paper_evaluation.json',
                     'exp4_vix_baseline_rolling_max_comparison.json']:
        obj = json.loads((output/filename).read_text())
        assert obj['is_synthetic'] is True
        assert obj['data_provenance']['source'] == 'deterministic_synthetic_smoke_test'
    obj = json.loads((output/'exp4_vix_metrics.json').read_text())
    assert obj['protocol']['primary_labels'] == 'paper'
    assert obj['protocol']['reference_labels'].startswith('fixed')
