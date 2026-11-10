import json
import numpy as np
import pandas as pd
import pytest
from run_experiments import main, run_project, demo_series


def test_offline_csv_realtime_run_writes_auditable_outputs(tmp_path):
    dates = pd.bdate_range('2000-01-03', periods=95)
    frame = pd.DataFrame({'date': dates, 'high': 20 + np.sin(np.arange(95) / 5)})
    source = tmp_path / 'input.csv'
    frame.to_csv(source, index=False)
    output = tmp_path / 'run'
    main(['--index', 'VIX', '--csv', str(source), '--experiments', '4',
          '--output', str(output), '--quiet'])
    meta = json.loads((output / 'run_metadata.json').read_text())
    metrics = json.loads((output / 'exp4_vix_metrics.json').read_text())
    warnings = pd.read_csv(output / 'exp4_vix_warning_data.csv')
    assert meta['status'] == 'completed'
    assert meta['is_synthetic'] is False
    assert len(warnings) == 95 - 89 + 1
    assert metrics['protocol']['reference_percentile'] == 95
    assert 'full_sample' in metrics and 'endpoint_censored' in metrics
    assert (output / 'exp4_vix_signals_major.csv').exists()
    assert len(meta['input']['series_sha256']) == 64
    assert 'input_highs.csv' in meta['outputs_sha256']
    assert 'src/signal_processing.py' in meta['source_sha256']
    # The same output location cannot accidentally mix old and new metrics.
    with pytest.raises(SystemExit):
        main(['--csv', str(source), '--experiments', '4', '--output', str(output), '--quiet'])


def test_cli_requires_explicit_data_source():
    with pytest.raises(SystemExit):
        main([])


def test_index_and_realtime_experiment_must_match():
    with pytest.raises(SystemExit):
        main(['--demo', '--index', 'VXO', '--experiments', '4'])


def test_python_api_preserves_return_value_manifest_and_output_guard(tmp_path, monkeypatch):
    from exp import exp1_rogue_wave_identification as experiment
    received = {}
    def fake_exp(index_name, highs, config, output, *, context):
        received.update(context)
        return {'observations': len(highs)}
    monkeypatch.setattr(experiment, 'run_exp1', fake_exp)
    highs = demo_series('VIX', n=20)
    original_attrs = dict(highs.attrs)
    result = run_project('VIX', highs, experiments=[1], output_dir=tmp_path / 'run')
    assert result['results'][1] == {'observations': 20}
    assert received['output_dir'] == result['output_dir']
    meta = json.loads((result['output_dir'] / 'run_metadata.json').read_text())
    assert meta['status'] == 'completed'
    assert meta['input']['source_rows'] == 20
    assert meta['input']['is_synthetic'] is True
    assert highs.attrs == original_attrs
    with pytest.raises(ValueError, match='not empty'):
        run_project('VIX', highs, experiments=[1], output_dir=result['output_dir'])


def test_failed_experiment_keeps_failed_manifest_and_input(tmp_path, monkeypatch):
    from exp import exp1_rogue_wave_identification as experiment
    def failing_exp(*args, **kwargs):
        raise RuntimeError('intentional numerical failure')
    monkeypatch.setattr(experiment, 'run_exp1', failing_exp)
    output = tmp_path / 'failed'
    with pytest.raises(RuntimeError, match='intentional numerical failure'):
        run_project('VIX', demo_series('VIX', n=20), experiments=[1], output_dir=output)
    meta = json.loads((output / 'run_metadata.json').read_text())
    assert meta['status'] == 'failed'
    assert meta['error'] == 'RuntimeError: intentional numerical failure'
    assert 'finished_utc' in meta
    assert (output / 'input_highs.csv').exists()


def test_input_snapshot_failure_is_also_recorded(tmp_path, monkeypatch):
    real_to_csv = pd.Series.to_csv
    def failing_snapshot(self, path_or_buf=None, *args, **kwargs):
        if getattr(path_or_buf, 'name', None) == 'input_highs.csv':
            raise OSError('intentional snapshot write failure')
        return real_to_csv(self, path_or_buf, *args, **kwargs)
    monkeypatch.setattr(pd.Series, 'to_csv', failing_snapshot)
    output = tmp_path / 'failed_snapshot'
    with pytest.raises(OSError, match='intentional snapshot write failure'):
        run_project('VIX', demo_series('VIX', n=20), experiments=[1], output_dir=output)
    meta = json.loads((output / 'run_metadata.json').read_text())
    assert meta['status'] == 'failed'
    assert 'snapshot write failure' in meta['error']


def test_demo_and_csv_apply_yaml_bounds_identically(tmp_path, monkeypatch):
    import yaml
    from data.data_loader import load_config
    from exp import exp1_rogue_wave_identification as experiment
    monkeypatch.setattr(experiment, 'run_exp1', lambda *args, **kwargs: None)
    series = demo_series('VIX')
    source = tmp_path / 'demo.csv'
    series.rename('high').to_csv(source)
    config = {**load_config('VIX'), 'sample_start': '2000-01-10', 'sample_end': '2000-02-01'}
    config_path = tmp_path / 'bounds.yaml'
    config_path.write_text(yaml.safe_dump(config))
    outputs = []
    for source_args, name in [(['--demo'], 'demo'), (['--csv', str(source)], 'csv')]:
        output = tmp_path / name
        main([*source_args, '--config', str(config_path), '--experiments', '1', '--output', str(output)])
        outputs.append(pd.read_csv(output / 'input_highs.csv'))
        meta = json.loads((output / 'run_metadata.json').read_text())
        assert meta['actual_start'] == '2000-01-10'
        assert meta['actual_end'] == '2000-02-01'
        assert meta['input']['source_rows'] == 320
    pd.testing.assert_frame_equal(outputs[0], outputs[1])


def test_effective_configuration_is_validated_after_cli_overrides(tmp_path, monkeypatch):
    import yaml
    from data.data_loader import load_config
    from exp import exp1_rogue_wave_identification as experiment
    monkeypatch.setattr(experiment, 'run_exp1', lambda *args, **kwargs: None)
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(yaml.safe_dump({**load_config('VIX'), 'filter_mode': 'invalid-old-value'}))
    output = tmp_path / 'run'
    main(['--demo', '--config', str(config_path), '--filter-mode', 'all_bins',
          '--labels', 'both', '--baseline', 'rolling_max', '--experiments', '1', '--output', str(output)])
    config = json.loads((output / 'run_metadata.json').read_text())['config']
    assert config['filter_mode'] == 'all_bins'
    assert config['labels'] == 'both'
    assert config['baseline'] == 'rolling_max'
    assert config['paper_diagnostics'] is False


def test_invalid_configuration_does_not_create_a_run(tmp_path):
    import yaml
    from data.data_loader import load_config
    config_path = tmp_path / 'bad.yaml'
    config_path.write_text(yaml.safe_dump({**load_config('VIX'), 'window_L': 80.5}))
    output = tmp_path / 'run'
    with pytest.raises(SystemExit):
        main(['--demo', '--config', str(config_path), '--output', str(output)])
    assert not output.exists()


@pytest.mark.parametrize('experiments', [[True], [1.5], [], '1,no', [6]])
def test_invalid_experiment_selection_does_not_create_a_run(tmp_path, experiments):
    output = tmp_path / 'run'
    with pytest.raises(ValueError, match='experiments'):
        run_project('VIX', demo_series('VIX', n=20), experiments=experiments, output_dir=output)
    assert not output.exists()


def test_direct_experiment_api_uses_outer_runner_without_changing_return_type(tmp_path):
    from exp.exp1_rogue_wave_identification import run_exp1
    output = tmp_path / 'direct'
    highs = demo_series('VIX', n=20)
    result = run_exp1('VIX', highs, output_dir=output)
    assert isinstance(result, dict)
    assert result['index'] == 'VIX'
    meta = json.loads((output / 'run_metadata.json').read_text())
    assert meta['status'] == 'completed'
    assert meta['experiments'] == [1]
    assert 'exp1_VIX_metrics.json' in meta['outputs_sha256']
    with pytest.raises(ValueError, match='not empty'):
        run_exp1('VIX', highs, output_dir=output)
