"""
Exp 4: Simulated real-time rogue-wave warning indicator on VIX.

Expanding-sample pipeline (no look-ahead):
- Full-sample ex post labels for evaluation only
- W_i = M_i * C_i; threshold=300
- Paper targets: >2.5xSWH: 75% detected, 0% false, 84.2% precision, 94.1% prec excl late
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


def run_exp4() -> dict:
    print('\n=== Experiment 4: Real-Time Warning Indicator on VIX ===')
    cfg = load_config('VIX')
    highs = load_daily_highs('VIX')
    print(f'VIX: {len(highs)} trading days ({highs.index[0].date()} to {highs.index[-1].date()})')
    
    # 1. Full-sample ex post labels (freeze endpoint)
    pct_desc = float(cfg.get('filter_percentile_descriptive', 92.5))
    x_full = highs.values.astype(float)
    dates_full = highs.index
    print(f'Computing full-sample envelope for ex post labels ({pct_desc}%)...')
    envelope_full = process_series(x_full, percentile_threshold=pct_desc)
    peak_df_full, swh = full_peak_analysis(dates_full, envelope_full)
    major_peaks = peak_df_full[peak_df_full['severity'] == 'major']
    lower_peaks = peak_df_full[peak_df_full['severity'].isin(['major','lower'])]
    print(f'Ex post: SWH={swh:.4f}, Major peaks: {len(major_peaks)}, Lower+major: {len(lower_peaks)}')
    
    # 2. Real-time simulation (95% filter, expanding window)
    pct_rt = float(cfg.get('filter_percentile_realtime', 95.0))
    threshold_warning = float(cfg.get('threshold_warning', 300))
    window_L = int(cfg.get('window_L', 80))
    block_len = int(cfg.get('block_len', 10))
    threshold_grad = int(cfg.get('threshold_grad_count', 50))
    
    print(f'Running real-time simulation (threshold_warning={threshold_warning})...')
    warning_df = run_realtime_simulation(
        series=highs,
        percentile_threshold=pct_rt,
        window_L=window_L,
        block_len=block_len,
        threshold_grad_count=threshold_grad,
    )
    print(f'Simulation complete: {len(warning_df)} days processed')
    
    # 3. First-signal detection
    w_series = pd.Series(warning_df['W_i'].values, index=pd.DatetimeIndex(warning_df['date']))
    first_signals = collapse_signal_runs(w_series, threshold=threshold_warning)
    print(f'First signal episodes: {len(first_signals)}')
    
    # 4. Evaluate against major (>2.5xSWH) and lower (>2xSWH) peaks
    all_metrics = {}
    for severity in ['major', 'lower']:
        cls_df = classify_first_signals(
            first_signal_dates=first_signals,
            peak_df=peak_df_full,
            severity=severity,
        )
        metrics = compute_detection_metrics(cls_df, peak_df_full, severity)
        all_metrics[severity] = metrics
        thresh_label = '>2.5xSWH' if severity == 'major' else '>2xSWH'
        print(f'\nPerformance ({thresh_label} peaks):')
        print(f'  Peaks detected:        {metrics["peaks_detected_pct"]:.1f}%  (paper: 75.0%)')
        print(f'  False signals:         {metrics["false_signal_pct"]:.1f}%   (paper: 0.0%)')
        print(f'  Precision:             {metrics["precision_pct"]:.1f}%  (paper: 84.2%)')
        print(f'  Precision excl late:   {metrics["precision_excl_late_pct"]:.1f}%  (paper: 94.1%)')
    
    # 5. Narrative check: 2008-10 and 2020-03 peaks
    detected_major_peaks = set()
    cls_major = classify_first_signals(first_signals, peak_df_full, severity='major')
    for _, row in cls_major.iterrows():
        if row['classification'] == 'detected' and row['associated_peak_date'] is not None:
            detected_major_peaks.add(pd.Timestamp(row['associated_peak_date']))
    
    crisis_2008 = major_peaks[(major_peaks['date'] >= '2008-09-01') & (major_peaks['date'] <= '2008-12-31')]
    crisis_2020 = major_peaks[(major_peaks['date'] >= '2020-02-01') & (major_peaks['date'] <= '2020-04-30')]
    print('\nNarrative checks:')
    print(f'  2008 crisis peaks: {list(crisis_2008["date"].dt.date)}')
    print(f'  2020 crisis peaks: {list(crisis_2020["date"].dt.date)}')
    
    # 6. Plotting
    envelope_series = pd.Series(envelope_full, index=dates_full)
    figure_warning_indicator(
        raw_series=highs,
        envelope=envelope_series,
        peak_df=peak_df_full,
        warning_df=warning_df,
        first_signals=first_signals,
        threshold_warning=threshold_warning,
        index_name='VIX',
        save_path=RESULTS / 'exp4_vix_warning.png'
    )
    
    # 7. Save metrics
    with open(RESULTS / 'exp4_vix_metrics.json', 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)
    
    warning_df.to_csv(RESULTS / 'exp4_vix_warning_data.csv', index=False)
    print('\nExperiment 4 complete. Results saved.')
    return all_metrics


if __name__ == '__main__':
    metrics = run_exp4()
