import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from data.data_loader import load_daily_highs, validate_daily_highs, load_config, series_digest


def test_csv_preserves_inclusive_endpoint_and_sorts(tmp_path):
    path = tmp_path / 'highs.csv'
    path.write_text('Date,High,Close\n2020-01-06,22,18\n2020-01-02,20,17\n2020-01-03,21,16\n')
    out = load_daily_highs('VIX', start='2020-01-03', end='2020-01-06', csv_path=path)
    assert out.tolist() == [21, 22]
    assert list(out.index) == [pd.Timestamp('2020-01-03'), pd.Timestamp('2020-01-06')]
    assert out.attrs['is_synthetic'] is False
    assert out.attrs['source_rows'] == 3
    assert out.attrs['series_sha256'] == series_digest(out)


def test_no_automatic_download_or_synthetic_fallback():
    with pytest.raises(ValueError, match='Supply --csv'):
        load_daily_highs('VXO')


def test_missing_high_is_not_replaced_by_close(tmp_path):
    path = tmp_path / 'wrong.csv'
    path.write_text('date,close\n2020-01-01,20\n')
    with pytest.raises(ValueError, match='high'):
        load_daily_highs('VIX', csv_path=path)


@pytest.mark.parametrize('values', [[20, np.nan], [20, np.inf], [20, 0], [20, -1]])
def test_bad_high_values_raise(values):
    with pytest.raises(ValueError):
        validate_daily_highs(pd.Series(values, index=pd.bdate_range('2020-01-01', periods=2)))


def test_duplicate_session_is_error_not_automatic_aggregation():
    index = pd.to_datetime(['2020-01-02 10:00', '2020-01-02 12:00'])
    with pytest.raises(ValueError, match='Duplicate'):
        validate_daily_highs(pd.Series([20, 21], index=index))


def test_yahoo_end_is_converted_to_exclusive_next_day(monkeypatch):
    calls = []
    def fake_download(*args, **kwargs):
        calls.append((args, kwargs))
        return pd.DataFrame({'High': [20., 21.]}, index=pd.to_datetime(['2020-01-03', '2020-01-06']))
    monkeypatch.setitem(sys.modules, 'yfinance', SimpleNamespace(download=fake_download))
    out = load_daily_highs('VIX', end='2020-01-06', source='yahoo')
    assert calls[0][1]['end'] == '2020-01-07'
    assert out.index[-1] == pd.Timestamp('2020-01-06')


def test_download_failure_never_substitutes_vix_for_vxo(monkeypatch):
    monkeypatch.setitem(sys.modules, 'yfinance', SimpleNamespace(download=lambda *a, **k: pd.DataFrame()))
    with pytest.raises(ValueError, match='no synthetic fallback'):
        load_daily_highs('VXO', source='yahoo')


def test_yahoo_single_row_does_not_squeeze_into_scalar(monkeypatch):
    frame = pd.DataFrame([[25.]], index=pd.to_datetime(['2020-01-06']),
                         columns=pd.MultiIndex.from_tuples([('High', '^VIX')]))
    monkeypatch.setitem(sys.modules, 'yfinance', SimpleNamespace(download=lambda *a, **k: frame))
    result = load_daily_highs('VIX', source='yahoo')
    assert isinstance(result, pd.Series)
    assert result.iloc[0] == 25.


def test_default_dates_do_not_confuse_peak_dates_with_source_endpoints():
    for index in ('VIX', 'VXO', 'VSTOXX'):
        config = load_config(index)
        assert config['sample_start'] is None
        assert config['sample_end'] is None


def test_ambiguous_case_insensitive_columns_are_rejected(tmp_path):
    path = tmp_path / 'ambiguous.csv'
    path.write_text('date,High,high\n2020-01-02,20,30\n')
    with pytest.raises(ValueError, match='unique ignoring case'):
        load_daily_highs('VIX', csv_path=path)


def test_outer_runner_can_apply_bounds_once_after_loading(tmp_path):
    from data.data_loader import prepare_daily_highs
    path = tmp_path / 'highs.csv'
    path.write_text('date,high\n2020-01-02,20\n2020-01-03,21\n2020-01-06,22\n')
    config = {**load_config('VIX'), 'sample_start': '2020-01-03', 'sample_end': '2020-01-06'}
    unbounded = load_daily_highs('VIX', csv_path=path, config=config, apply_bounds=False)
    assert len(unbounded) == 3
    prepared = prepare_daily_highs(unbounded, 'VIX', config['sample_start'], config['sample_end'])
    assert prepared.tolist() == [21, 22]
    assert prepared.attrs['source_rows'] == 3
    assert prepared.attrs['source_file_sha256'] == unbounded.attrs['source_file_sha256']
    assert prepared.attrs['series_sha256'] == series_digest(prepared)
    assert len(unbounded) == 3
