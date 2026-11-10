"""Validate the complete effective protocol before any run is started."""
from __future__ import annotations

from datetime import date, datetime
from numbers import Integral, Real

import numpy as np
import pandas as pd


_INTEGER_FIELDS = {
    'window_L': 3, 'block_len': 2, 'detection_window_days': 1,
    'min_inter_peak_days': 0, 'late_signal_days': 0,
}
_FLOAT_FIELDS = {
    'filter_percentile_descriptive', 'filter_percentile_realtime',
    'threshold_lower_extreme', 'threshold_major_rogue', 'delta_t',
    'threshold_grad_count', 'threshold_warning',
}
_DATE_FIELDS = {'sample_start', 'sample_end', 'insample_end'}
_CHOICES = {
    'filter_mode': {'spectral_peaks', 'all_bins'},
    'boundary_condition': {'dirichlet', 'dirichlet_ghost'},
    'labels': {'own', 'paper', 'both'},
    'baseline': {None, 'rolling_max'},
}
_OPTIONAL_DEFAULTS = {'labels': 'own', 'baseline': None, 'paper_diagnostics': False}
_REQUIRED = set(_INTEGER_FIELDS) | _FLOAT_FIELDS | _DATE_FIELDS | {
    'index', 'filter_mode', 'boundary_condition',
}


def session_date(value, field: str):
    """Accept an ISO-like date/date object, never a numeric timestamp or time."""
    if value is None:
        return None
    if not isinstance(value, (str, date, datetime, pd.Timestamp)):
        raise ValueError(f'{field} must be a session date or null')
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{field} must be a valid session date') from exc
    if pd.isna(timestamp) or timestamp.tz is not None or timestamp != timestamp.normalize():
        raise ValueError(f'{field} must be a valid date without a time or timezone')
    return timestamp.strftime('%Y-%m-%d')


def validate_config(config: dict, index_name: str) -> dict:
    """Return a canonical copy; reject unknown keys and silent coercions.

    Call after CLI overrides, so validation describes the protocol that will
    actually run. Published defaults remain in the three explicit YAML files.
    """
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a mapping')
    upper = index_name.upper()
    if upper not in {'VIX', 'VXO', 'VSTOXX'}:
        raise ValueError(f'Unknown index: {index_name}')
    allowed = _REQUIRED | set(_OPTIONAL_DEFAULTS)
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f'Unknown configuration fields: {sorted(unknown, key=str)}')
    missing = _REQUIRED - set(config)
    if missing:
        raise ValueError(f'Missing configuration fields: {sorted(missing)}')
    cfg = {**_OPTIONAL_DEFAULTS, **config}
    if not isinstance(cfg['index'], str) or cfg['index'].upper() != upper:
        raise ValueError('Config index does not match requested index')
    cfg['index'] = upper
    for name, minimum in _INTEGER_FIELDS.items():
        value = cfg[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
            raise ValueError(f'{name} must be an integer >= {minimum}')
        cfg[name] = int(value)
    for name in _FLOAT_FIELDS:
        value = cfg[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
        cfg[name] = float(value)
    for name in ('filter_percentile_descriptive', 'filter_percentile_realtime'):
        if not 0 <= cfg[name] <= 100:
            raise ValueError(f'{name} must lie in [0, 100]')
    for name in ('delta_t', 'threshold_lower_extreme', 'threshold_major_rogue'):
        if cfg[name] <= 0:
            raise ValueError(f'{name} must be positive')
    for name in ('threshold_grad_count', 'threshold_warning'):
        if cfg[name] < 0:
            raise ValueError(f'{name} must be nonnegative')
    if cfg['threshold_lower_extreme'] >= cfg['threshold_major_rogue']:
        raise ValueError('threshold_lower_extreme must be less than threshold_major_rogue')
    for name, choices in _CHOICES.items():
        if not (isinstance(cfg[name], str) or cfg[name] is None) or cfg[name] not in choices:
            raise ValueError(f'{name} must be one of {sorted(choices, key=str)}')
    if not isinstance(cfg['paper_diagnostics'], (bool, np.bool_)):
        raise ValueError('paper_diagnostics must be a boolean')
    cfg['paper_diagnostics'] = bool(cfg['paper_diagnostics'])
    for name in _DATE_FIELDS:
        cfg[name] = session_date(cfg[name], name)
    if cfg['sample_start'] and cfg['sample_end'] and cfg['sample_start'] > cfg['sample_end']:
        raise ValueError('sample_start must not be after sample_end')
    return cfg
