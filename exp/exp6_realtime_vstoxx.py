"""
Exp 6: Real-time warning on VSTOXX (European market generalization).

Same pipeline as VIX/VXO but:
- threshold_warning = 300 (VSTOXX-specific)
- Paper: 87.5% detected (>2.5xSWH), 11.8% false, misses 2016 event
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


def run_exp6() -> dict:
    print('\n=== Experiment 6: Real-Time Warning Indicator on VSTOXX ===')
    cfg = load_config('VSTOXX')
    highs = load_daily_highs('VSTOXX')
    print(f'VSTOXX: {len(highs)} trading days ({highs.index[0].date()} to {highs.index[-1].date()})')
    
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
    threshold_warning = float(cfg.get('threshold_warning', 300))
    window_L = int(cfg.get('window_L', 80))
    block_len = int(cfg.get('block_len', 10))
    threshold_grad = int(cfg.get('threshold_grad_count', 50))
    
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
        all_metrics[severity] = metrics
        thresh_label = '>2.5xSWH' if severity == 'major' else '>2xSWH'
        print(f'\nPerformance ({thresh_label}):')
        print(f'  Peaks detected: {metrics["peaks_detected_pct"]:.1f}% (paper: {87.5 if severity=="major" else 88.9}%)')
        print(f'  False signals:  {metrics["false_signal_pct"]:.1f}% (paper: 11.8%)')
        print(f'  Precision:      {metrics["precision_pct"]:.1f}% (paper: {70.6 if severity=="major" else 76.5}%)')
    
    # Narrative: check 2016 event
    peaks_2016 = major_peaks[(major_peaks['date'] >= '2016-01-01') & (major_peaks['date'] <= '2016-12-31')]
    if not peaks_2016.empty:
        print(f'\n2016 event dates: {list(peaks_2016["date"].dt.date)}')
        # Check if detected
        cls_major = classify_first_signals(first_signals, peak_df_full, severity='major')
        detected_dates = cls_major[cls_major['classification']=='detected']['associated_peak_date'].dropna()
        detected_2016 = [d for d in detected_dates if pd.Timestamp(d).year == 2016]
        if detected_2016:
            print(f'  2016 event: DETECTED (signal found)')
        else:
            print(f'  2016 event: MISSED (consistent with paper narrative)')
    else:
        print('No major peaks in 2016 found in this sample.')
    
    # Plot
    envelope_series = pd.Series(envelope_full, index=dates_full)
    figure_warning_indicator(
        raw_series=highs,
        envelope=envelope_series,
        peak_df=peak_df_full,
        warning_df=warning_df,
        first_signals=first_signals,
        threshold_warning=threshold_warning,
        index_name='VSTOXX',
        save_path=RESULTS / 'exp6_vstoxx_warning.png'
    )
    
    with open(RESULTS / 'exp6_vstoxx_metrics.json', 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    warning_df.to_csv(RESULTS / 'exp6_vstoxx_warning_data.csv', index=False)
    print('\nExperiment 6 complete.')
    return all_metrics


if __name__ == '__main__':
    metrics = run_exp6()
