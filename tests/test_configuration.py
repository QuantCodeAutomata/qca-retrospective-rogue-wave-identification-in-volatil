from datetime import date

import numpy as np
import pytest

from data.data_loader import load_config
from src.configuration import validate_config


@pytest.mark.parametrize('index', ['VIX', 'VXO', 'VSTOXX'])
def test_default_configs_validate_without_changing_published_parameters(index):
    original = load_config(index)
    result = validate_config(original, index)
    assert result['window_L'] == 80
    assert result['block_len'] == 10
    assert result['threshold_warning'] == original['threshold_warning']
    assert result['labels'] == 'own'
    assert result['baseline'] is None
    assert result['paper_diagnostics'] is False
    assert 'labels' not in original


@pytest.mark.parametrize('field,value', [
    ('window_L', 80.5), ('window_L', True), ('window_L', 2),
    ('block_len', '10'), ('block_len', 1), ('detection_window_days', 0),
    ('late_signal_days', -1), ('min_inter_peak_days', False),
    ('delta_t', 0), ('delta_t', np.inf), ('threshold_warning', np.nan),
    ('threshold_grad_count', True), ('threshold_grad_count', -1),
    ('filter_percentile_realtime', 101), ('filter_percentile_descriptive', -1),
    ('filter_mode', 'best'), ('boundary_condition', 'periodic'),
    ('labels', 'future'), ('baseline', 'vix'), ('paper_diagnostics', 'true'),
    ('sample_start', 'not-a-date'), ('sample_end', 'NaT'),
    ('sample_start', 20200101), ('sample_end', '2020-01-01T12:00:00'),
    ('insample_end', '2020-01-01T00:00:00Z'),
])
def test_invalid_config_field_is_named(field, value):
    config = {**load_config('VIX'), field: value}
    with pytest.raises(ValueError, match=field):
        validate_config(config, 'VIX')


def test_unknown_missing_and_inconsistent_config_are_errors():
    config = load_config('VIX')
    with pytest.raises(ValueError, match='misspelled'):
        validate_config({**config, 'misspelled': 5}, 'VIX')
    with pytest.raises(ValueError, match='window_L'):
        validate_config({k: v for k, v in config.items() if k != 'window_L'}, 'VIX')
    with pytest.raises(ValueError, match='index'):
        validate_config(config, 'VXO')
    with pytest.raises(ValueError, match='threshold_lower_extreme'):
        validate_config({**config, 'threshold_lower_extreme': 3.0}, 'VIX')
    with pytest.raises(ValueError, match='sample_start'):
        validate_config({**config, 'sample_start': '2020-02-01', 'sample_end': '2020-01-01'}, 'VIX')


def test_yaml_date_values_are_canonicalized_without_changing_input():
    config = {**load_config('VIX'), 'sample_start': date(2020, 1, 2)}
    result = validate_config(config, 'VIX')
    assert result['sample_start'] == '2020-01-02'
    assert config['sample_start'] == date(2020, 1, 2)
