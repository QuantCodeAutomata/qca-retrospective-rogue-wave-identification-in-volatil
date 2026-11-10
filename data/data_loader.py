"""Explicit, validated daily HIGH data. Never substitute one index for another.

Dates denote exchange trading sessions. Requested start/end dates are INCLUSIVE.
CSV input needs one row per observed trading session, normally ``date,high``.
The actual observations, rather than a generic weekday calendar, define a trading day.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.configuration import session_date

INDEX_TICKER_MAP = {'VIX': '^VIX', 'VXO': '^VXO', 'VSTOXX': '^V2TX'}
CONFIG_DIR = Path(__file__).resolve().parents[1] / 'configs'


def load_config(index_name: str, config_path: str | Path | None = None) -> dict:
    upper = index_name.upper()
    if upper not in INDEX_TICKER_MAP:
        raise ValueError(f'Unknown index: {index_name}')
    path = Path(config_path) if config_path else CONFIG_DIR / f'{upper.lower()}.yaml'
    with path.open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f'Configuration must be a mapping: {path}')
    if not isinstance(config.get('index', upper), str) or config.get('index', upper).upper() != upper:
        raise ValueError('Config index does not match requested index')
    return config


def validate_daily_highs(series: pd.Series, index_name: str = 'INDEX') -> pd.Series:
    """Reject missing, nonfinite, nonpositive or duplicate observations; sort dates.

    No filling, interpolation, resampling, or synthetic replacement is performed.
    Timezone information is removed without shifting the local session date.
    """
    if not isinstance(series, pd.Series) or series.empty:
        raise ValueError('Daily highs must be a nonempty pandas Series')
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError('Daily highs must have a DatetimeIndex')
    dates = series.index
    if dates.hasnans:
        raise ValueError('Missing session dates are not allowed')
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    dates = dates.normalize()
    if dates.has_duplicates:
        duplicates = dates[dates.duplicated()].strftime('%Y-%m-%d').tolist()[:5]
        raise ValueError(f'Duplicate daily sessions: {duplicates}')
    values = pd.to_numeric(series, errors='raise').to_numpy(dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError('High values must be finite; NaN/inf must be resolved at the source')
    if np.any(values <= 0):
        raise ValueError('Volatility-index High values must be strictly positive')
    result = pd.Series(values, index=dates, name=f'{index_name.upper()}_High').sort_index()
    result.index.name = 'date'
    result.attrs.update(series.attrs)
    return result


def series_digest(series: pd.Series) -> str:
    canonical = series.rename('high').to_csv(date_format='%Y-%m-%d', float_format='%.17g')
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def prepare_daily_highs(series: pd.Series, index_name: str, start=None, end=None) -> pd.Series:
    """Validate and apply the same inclusive bounds to CSV, demo and API data."""
    requested_start = session_date(start, 'sample_start')
    requested_end = session_date(end, 'sample_end')
    if requested_start and requested_end and requested_start > requested_end:
        raise ValueError('sample_start must not be after sample_end')
    result = validate_daily_highs(series, index_name)
    source_rows = result.attrs.get('source_rows', len(result))
    if requested_start:
        result = result.loc[result.index >= pd.Timestamp(requested_start)].copy()
    if requested_end:
        result = result.loc[result.index <= pd.Timestamp(requested_end)].copy()
    if result.empty:
        raise ValueError('No observations remain in the requested inclusive date range')
    result.attrs.update({'requested_start_inclusive': requested_start,
                         'requested_end_inclusive': requested_end,
                         'source_rows': source_rows, 'used_rows': len(result),
                         'actual_start': str(result.index[0].date()),
                         'actual_end': str(result.index[-1].date()),
                         'weekend_rows': int((result.index.dayofweek >= 5).sum()),
                         'series_sha256': series_digest(result)})
    return result


def load_daily_highs(
    index_name: str,
    start: str | None = None,
    end: str | None = None,
    *,
    csv_path: str | Path | None = None,
    source: str = 'csv',
    date_column: str = 'date',
    high_column: str = 'high',
    config: dict | None = None,
    apply_bounds: bool = True,
) -> pd.Series:
    """Read a supplied CSV, or explicitly request Yahoo (optional dependency).

    Source failure is an error. CSV is the default and has no network dependency.
    Data provenance is attached to ``Series.attrs`` and saved by the runner.
    ``apply_bounds=False`` leaves validation/slicing to the shared outer runner;
    an explicit Yahoo query still uses the requested provider bounds.
    """
    upper = index_name.upper()
    cfg = config if config is not None else load_config(upper)
    requested_start = session_date(start if start is not None else cfg.get('sample_start'), 'sample_start')
    requested_end = session_date(end if end is not None else cfg.get('sample_end'), 'sample_end')
    if requested_start and requested_end and pd.Timestamp(requested_start) > pd.Timestamp(requested_end):
        raise ValueError('start must not be after end')
    if csv_path is not None:
        path = Path(csv_path).expanduser().resolve()
        frame = pd.read_csv(path)
        columns = {str(c).casefold(): c for c in frame.columns}
        if len(columns) != len(frame.columns):
            raise ValueError('CSV column names must be unique ignoring case')
        try:
            dcol, hcol = columns[date_column.casefold()], columns[high_column.casefold()]
        except KeyError as exc:
            raise ValueError(f'CSV must contain {date_column!r} and {high_column!r}; got {list(frame.columns)}') from exc
        dates = pd.DatetimeIndex(pd.to_datetime(frame[dcol], errors='raise'))
        series = pd.Series(frame[hcol].to_numpy(), index=dates)
        provenance = {'source': 'local_csv', 'source_file': path.name,
                      'source_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'date_column': str(dcol), 'high_column': str(hcol),
                      'is_synthetic': False, 'index_identity': 'asserted_by_input_owner'}
    elif source == 'yahoo':
        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError('Install requirements-download.txt to use --source yahoo, or supply --csv') from exc
        yahoo_end = (pd.Timestamp(requested_end).normalize() + pd.Timedelta(days=1)).strftime('%Y-%m-%d') if requested_end else None
        frame = yf.download(INDEX_TICKER_MAP[upper], start=requested_start or '1900-01-01',
                            end=yahoo_end, progress=False, auto_adjust=False)
        if frame.empty or 'High' not in frame:
            raise ValueError(f'No real HIGH observations returned for {upper}. Supply a vendor CSV; no synthetic fallback exists.')
        high = frame['High']
        if isinstance(high, pd.DataFrame):
            if high.shape[1] != 1:
                raise ValueError('Expected exactly one downloaded ticker')
            high = high.iloc[:, 0]
        series = high
        provenance = {'source': 'yahoo', 'ticker': INDEX_TICKER_MAP[upper], 'is_synthetic': False}
    else:
        raise ValueError('Supply --csv PATH, or explicitly choose --source yahoo')
    series.attrs.update(provenance)
    return prepare_daily_highs(series, upper, requested_start, requested_end) if apply_bounds else series
