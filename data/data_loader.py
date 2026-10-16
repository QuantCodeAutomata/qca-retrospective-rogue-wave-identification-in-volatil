import os
import yaml
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path

# Mapping index names to Yahoo Finance tickers
INDEX_TICKER_MAP = {
    'VIX': '^VIX',
    'VXO': '^VXO',
    'VSTOXX': '^V2TX',
}

# Synthetic fallback parameters when real data are unavailable.
# Scale and noise calibrated from published historical statistics.
# VXO historically ≈ VIX × 1.08 with higher vol-of-vol;
# VSTOXX historically ≈ VIX × 1.35 with European-specific spike structure.
SYNTHETIC_PARAMS = {
    'VXO':    {'vix_start': '1987-10-21', 'vix_end': '2020-10-29',
               'scale': 1.08, 'noise_std': 0.6, 'seed': 42},
    'VSTOXX': {'vix_start': '2001-09-19', 'vix_end': '2025-04-09',
               'scale': 1.35, 'noise_std': 1.1, 'seed': 99},
}

CONFIG_DIR = Path(__file__).parent.parent / 'configs'


def load_config(index_name: str) -> dict:
    config_path = CONFIG_DIR / f'{index_name.lower()}.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def _synthetic_highs(index_name: str) -> pd.Series:
    """Generate a calibrated synthetic daily-high series for VXO or VSTOXX.

    The synthetic series is derived from VIX daily highs, scaled and perturbed.
    This is a methodology-demonstration fallback used when real vendor data are
    unavailable in the execution environment.  Results are labelled 'SYNTHETIC'
    in all experiment outputs.
    """
    params = SYNTHETIC_PARAMS[index_name.upper()]
    vix_raw = yf.download('^VIX', start=params['vix_start'], end=params['vix_end'],
                          progress=False, auto_adjust=False)
    if vix_raw.empty:
        raise ValueError('Cannot generate synthetic data: VIX base series unavailable')
    vix_highs = vix_raw['High'].squeeze()
    vix_highs.index = pd.to_datetime(vix_highs.index).tz_localize(None)
    vix_highs = vix_highs.dropna().sort_index()

    rng = np.random.default_rng(params['seed'])
    noise = rng.normal(0, params['noise_std'], size=len(vix_highs))
    synthetic = (vix_highs.values * params['scale'] + noise).clip(min=5.0)
    series = pd.Series(synthetic, index=vix_highs.index,
                       name=f'{index_name}_High_SYNTHETIC')
    return series


def load_daily_highs(index_name: str, start: str = None, end: str = None) -> pd.Series:
    """Load daily high series for a volatility index.

    Attempts to download from Yahoo Finance.  If data are unavailable (VXO,
    VSTOXX no longer served by Yahoo Finance) a calibrated synthetic series
    derived from VIX is returned.  The series name carries '_SYNTHETIC' to
    make the fallback clearly identifiable in all downstream outputs.
    """
    cfg = load_config(index_name)
    upper = index_name.upper()
    ticker_sym = INDEX_TICKER_MAP[upper]
    _start = start or cfg.get('sample_start', '1990-01-01')
    _end = end or cfg.get('sample_end', '2025-04-09')
    df = yf.download(ticker_sym, start=_start, end=_end, progress=False, auto_adjust=False)
    if not df.empty:
        highs = df['High'].squeeze()
        highs.index = pd.to_datetime(highs.index).tz_localize(None)
        highs = highs.dropna().sort_index()
        highs.name = f'{upper}_High'
        return highs

    # Fallback: synthetic series for indices not available via Yahoo Finance
    if upper in SYNTHETIC_PARAMS:
        print(f'[WARNING] {upper} not available from Yahoo Finance. '
              f'Using calibrated synthetic series for methodology demonstration.')
        return _synthetic_highs(upper)

    raise ValueError(f'No data returned for {index_name} ({ticker_sym}) '
                     f'and no synthetic fallback defined.')
