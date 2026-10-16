"""
Exp 5: Real-time warning on VXO (out-of-sample generalization).

Same pipeline as VIX but:
- threshold_warning = 700 (VXO-specific)
- In-sample: up to 2004-12-31; Out-of-sample: 2005 onward
- Paper targets: >2.5xSWH: 87.5% detected, 15.8% false, 63.2% precision
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import json

from data.data_loader import load_daily_highs, load_config
from src.signal_processing import process_series
from src.peak_detection import full_peak_analysis
from src.realtime_pipeline import run_realtime_simulation
from src.evaluation import collapse_signal_runs, classify_first_signals, compute_detection_metrics
from src.plotting import figure_warning_indicator

RESULTS = Path('results')
RESULTS.mkdir(exist_ok=True)


def run_exp5() -> dict:
    print('\n=== Experiment 5: Real-Time Warning Indicator on VXO ===')
    cfg = load_config('VXO')
    highs = load_daily_highs('VXO')
    print(f'VXO: {len(highs)} trading days ({highs.index[0].date()} to {highs.index[-1].date()})')
    
    # 1. Full-sample ex post labels
    pct_desc = float(cfg.get('filter_percentile_descriptive', 92.5))
    x_full = highs.values.astype(float)
    dates_full = highs.index
    print(f'Computing full-sample envelope ({pct_desc}%)...')
    envelope_full = process_series(x_full, percentile_threshold=pct_desc)
    peak_df_full, swh = full_peak_analysis(dates_full, envelope_full)
    major_peaks = peak_df_full[peak_df_full['severity'] == 'major']
    print(f'SWH={swh:.4f}, Major peaks: {len(major_peaks)}')
    
    # 2. Real-time simulation
    pct_rt = float(cfg.get('filter_percentile_realtime', 95.0))
    threshold_warning = float(cfg.get('threshold_warning', 700))
    window_L = int(cfg.get('window_L', 80))
    block_len = int(cfg.get('block_len', 10))
    threshold_grad = int(cfg.get('threshold_grad_count', 50))
    insample_end = cfg.get('insample_end', '2004-12-31')
    
    print(f'Running real-time simulation (threshold={threshold_warning})...')
    warning_df = run_realtime_simulation(
        series=highs,
        percentile_threshold=pct_rt,
        window_L=window_L,
        block_len=block_len,
        threshold_grad_count=threshold_grad,
    )
    print(f'Simulation complete: {len(warning_df)} days')
    
    # 3. First signals
    w_series = pd.Series(warning_df['W_i'].values, index=pd.DatetimeIndex(warning_df['date']))
    first_signals = collapse_signal_runs(w_series, threshold=threshold_warning)
    print(f'First signals: {len(first_signals)}')
    
    all_metrics = {}
    for severity in ['major', 'lower']:
        cls_df = classify_first_signals(first_signals, peak_df_full, severity=severity)
        metrics = compute_detection_metrics(cls_df, peak_df_full, severity)
        all_metrics[f'{severity}_full'] = metrics
        thresh_label = '>2.5xSWH' if severity == 'major' else '>2xSWH'
        print(f'\nFull sample ({thresh_label}):')
        print(f'  Peaks detected: {metrics["peaks_detected_pct"]:.1f}% (paper: {87.5 if severity=="major" else 76.9}%)')
        print(f'  False signals:  {metrics["false_signal_pct"]:.1f}% (paper: 15.8%)')
        print(f'  Precision:      {metrics["precision_pct"]:.1f}% (paper: {63.2 if severity=="major" else 73.7}%)')
    
    # Out-of-sample metrics (2005 onward)
    oos_signals = first_signals[first_signals >= pd.Timestamp('2005-01-01')]
    oos_peaks = peak_df_full[peak_df_full['date'] >= pd.Timestamp('2005-01-01')]
    for severity in ['major']:
        cls_oos = classify_first_signals(oos_signals, oos_peaks, severity=severity)
        metrics_oos = compute_detection_metrics(cls_oos, oos_peaks, severity)
        all_metrics[f'{severity}_oos'] = metrics_oos
        print(f'\nOut-of-sample (2005+, major):')
        print(f'  Peaks detected: {metrics_oos["peaks_detected_pct"]:.1f}%')
        print(f'  Paper narrative: 7 of 8 major peaks detected out-of-sample')
    
    # Plot
    envelope_series = pd.Series(envelope_full, index=dates_full)
    figure_warning_indicator(
        raw_series=highs,
        envelope=envelope_series,
        peak_df=peak_df_full,
        warning_df=warning_df,
        first_signals=first_signals,
        threshold_warning=threshold_warning,
        index_name='VXO',
        insample_end=str(insample_end),
        save_path=RESULTS / 'exp5_vxo_warning.png'
    )
    
    with open(RESULTS / 'exp5_vxo_metrics.json', 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    warning_df.to_csv(RESULTS / 'exp5_vxo_warning_data.csv', index=False)
    print('\nExperiment 5 complete.')
    return all_metrics


if __name__ == '__main__':
    metrics = run_exp5()
