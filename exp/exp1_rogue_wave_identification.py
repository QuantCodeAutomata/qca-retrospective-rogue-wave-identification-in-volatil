"""
Exp 1: Retrospective rogue-wave identification in volatility index high series.

Processed-envelope pipeline: mirror + FFT denoising (92.5%) + Hilbert envelope.
Optional raw-series comparison.
Ambi guous implementation choices documented:
  - Mirror: symmetric reflection excluding endpoint duplicate [x[0]..x[N-1],x[N-2]..x[1]]
  - Spectral filter: detect amplitude-spectrum peaks, keep top >=92.5th percentile
  - SWH = mean of top ceil(N_peaks/3) prominences
  - find_peaks: default settings
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
import json

from data.data_loader import load_daily_highs, load_config
from src.signal_processing import process_series
from src.peak_detection import full_peak_analysis, detect_peaks_and_prominences, compute_swh
from src.plotting import figure1_style, histogram_raw_peaks, histogram_prominences

RESULTS = Path('results')
RESULTS.mkdir(exist_ok=True)


def run_exp1(index_name: str = 'VIX') -> dict:
    print(f'\n=== Experiment 1: {index_name} ===')
    cfg = load_config(index_name)
    
    # Load daily highs
    highs = load_daily_highs(index_name)
    print(f'Loaded {len(highs)} trading days: {highs.index[0].date()} to {highs.index[-1].date()}')
    
    x = highs.values.astype(float)
    dates = highs.index
    
    # 1. Processed-envelope mode (92.5% threshold for descriptive analysis)
    pct_threshold = float(cfg.get('filter_percentile_descriptive', 92.5))
    print(f'Computing processed envelope with {pct_threshold}% FFT threshold...')
    envelope = process_series(x, percentile_threshold=pct_threshold)
    envelope_series = pd.Series(envelope, index=dates, name=f'{index_name}_Envelope')
    
    # 2. Peak analysis on processed envelope
    peak_df, swh = full_peak_analysis(
        dates=dates,
        envelope=envelope,
        threshold_lower=float(cfg.get('threshold_lower_extreme', 2.0)),
        threshold_major=float(cfg.get('threshold_major_rogue', 2.5)),
    )
    
    major_peaks = peak_df[peak_df['severity'] == 'major']
    lower_peaks = peak_df[peak_df['severity'] == 'lower']
    n_major = len(major_peaks)
    n_lower = len(lower_peaks)
    
    print(f'\nSWH = {swh:.4f}')
    print(f'Total envelope peaks: {len(peak_df)}')
    print(f'Major peaks (>2.5*SWH): {n_major}')
    print(f'Lower extremes (>2*SWH, not major): {n_lower}')
    
    print('\nMajor rogue-wave peaks:')
    print(major_peaks[['date','envelope_value','prominence']].to_string(index=False))
    
    print('\nLower extreme peaks:')
    print(lower_peaks[['date','envelope_value','prominence']].to_string(index=False))
    
    # 3. Plotting
    figure1_style(
        raw_series=highs,
        envelope=envelope_series,
        peak_df=peak_df,
        index_name=index_name,
        save_path=RESULTS / f'exp1_{index_name}_envelope_overlay.png'
    )
    histogram_raw_peaks(
        raw_series=highs,
        index_name=index_name,
        save_path=RESULTS / f'exp1_{index_name}_histogram_raw.png'
    )
    histogram_prominences(
        peak_df=peak_df,
        swh=swh,
        index_name=index_name,
        save_path=RESULTS / f'exp1_{index_name}_histogram_prominences.png'
    )
    
    # 4. Raw series comparison (optional)
    raw_peaks, raw_proms = detect_peaks_and_prominences(x)
    raw_swh = compute_swh(raw_proms)
    print(f'\nRaw-series comparison: {len(raw_peaks)} peaks, SWH={raw_swh:.4f}')
    print(f'Processed envelope: {len(peak_df)} peaks, SWH={swh:.4f} (more structured)')
    
    return {
        'swh': swh,
        'n_major': n_major,
        'n_lower': n_lower,
        'peak_df': peak_df,
        'swh_threshold_used': pct_threshold,
        'raw_swh': raw_swh,
        'n_raw_peaks': len(raw_peaks),
    }


if __name__ == '__main__':
    all_results = {}
    md_lines = ['# Experiment 1: Rogue-Wave Peak Tables\n']
    
    for idx_name in ['VIX', 'VXO', 'VSTOXX']:
        try:
            res = run_exp1(idx_name)
            all_results[idx_name] = {
                'swh': res['swh'],
                'n_major': res['n_major'],
                'n_lower': res['n_lower'],
                'n_all_peaks': len(res['peak_df']),
                'raw_swh': res['raw_swh'],
                'n_raw_peaks': res['n_raw_peaks'],
            }
            md_lines.append(f'\n## {idx_name}\n')
            md_lines.append(f'- SWH (processed): {res["swh"]:.4f}\n')
            md_lines.append(f'- Major peaks (>2.5xSWH): {res["n_major"]}\n')
            md_lines.append(f'- Lower extremes (>2xSWH): {res["n_lower"]}\n')
            md_lines.append(f'- Total envelope peaks: {len(res["peak_df"])}\n')
            md_lines.append(f'- Raw series SWH: {res["raw_swh"]:.4f}, Raw peaks: {res["n_raw_peaks"]}\n')
            md_lines.append('\n### Major peaks\n')
            major = res['peak_df'][res['peak_df']['severity']=='major']
            if not major.empty:
                md_lines.append(major[['date','envelope_value','prominence']].to_markdown(index=False) + '\n')
            md_lines.append('\n### Lower extreme peaks\n')
            lower = res['peak_df'][res['peak_df']['severity']=='lower']
            if not lower.empty:
                md_lines.append(lower[['date','envelope_value','prominence']].to_markdown(index=False) + '\n')
        except Exception as e:
            print(f'ERROR for {idx_name}: {e}')
            all_results[idx_name] = {'error': str(e)}
    
    # Save markdown summary
    with open(RESULTS / 'exp1_peak_tables.md', 'w') as f:
        f.writelines(md_lines)
    
    # Save JSON
    json_results = {k: {kk: vv for kk, vv in v.items() if kk != 'peak_df'} for k, v in all_results.items()}
    with open(RESULTS / 'exp1_results.json', 'w') as f:
        json.dump(json_results, f, indent=2, default=str)
    
    print('\nExperiment 1 complete. Results saved to results/')
