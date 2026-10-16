"""
Exp 2: Retrospective Localization and Schrodinger Eigenanalysis.

For each 80-day rolling window:
 - Construct U = -|psi|^2
 - Build Dirichlet-BC Hamiltonian H
 - Solve for lambda_min and v_min
 - Compute width (2nd moment), localization distance, potential skewness/kurtosis
Bin by days-to-next-major-peak (0-5, 5-30, >30).
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
from src.schrodinger import rolling_schrodinger_analysis
from src.diagnostics import assign_days_to_next_peak, bin_by_days_to_peak
from src.plotting import figure2_style_density

RESULTS = Path('results')
RESULTS.mkdir(exist_ok=True)


def run_exp2(index_name: str = 'VIX') -> pd.DataFrame:
    print(f'\n=== Experiment 2: Schrodinger Eigenanalysis ({index_name}) ===')
    cfg = load_config(index_name)
    highs = load_daily_highs(index_name)
    x = highs.values.astype(float)
    dates = highs.index
    
    # 1. Process envelope (92.5% for descriptive)
    pct = float(cfg.get('filter_percentile_descriptive', 92.5))
    print(f'Processing envelope ({pct}% threshold)...')
    envelope = process_series(x, percentile_threshold=pct)
    
    # 2. Ex post peak labels for days-to-next-peak
    peak_df, swh = full_peak_analysis(dates, envelope)
    major_peaks = peak_df[peak_df['severity'] == 'major']
    major_peak_dates = pd.DatetimeIndex(major_peaks['date'])
    print(f'SWH={swh:.4f}, Major peaks: {len(major_peaks)}')
    
    # 3. Rolling Schrodinger analysis
    window_L = int(cfg.get('window_L', 80))
    print(f'Running rolling Schrodinger analysis (L={window_L})...')
    diag_df = rolling_schrodinger_analysis(dates, envelope, window_L=window_L)
    print(f'Analysis complete: {len(diag_df)} windows')
    
    # 4. Days to next peak
    window_dates = pd.DatetimeIndex(diag_df['date'])
    days_series = assign_days_to_next_peak(window_dates, major_peak_dates)
    diag_df['days_to_next_peak'] = days_series.values
    diag_df['bin_label'] = bin_by_days_to_peak(days_series).values
    
    # 5. Summary statistics per bin
    metrics = ['width', 'loc_distance', 'skewness', 'kurtosis']
    print('\nDiagnostics by bin:')
    for metric in metrics:
        print(f'\n  {metric}:')
        for bin_lbl in ['0-5', '5-30', '>30']:
            subset = diag_df[diag_df['bin_label'] == bin_lbl][metric].dropna()
            if len(subset) > 0:
                print(f'    {bin_lbl}: n={len(subset)}, mean={subset.mean():.3f}, std={subset.std():.3f}, median={subset.median():.3f}')
    
    # 6. Plot KDE for each metric by bin
    for metric in metrics:
        figure2_style_density(
            diagnostic_df=diag_df,
            metric=metric,
            index_name=index_name,
            save_path=RESULTS / f'exp2_{index_name}_{metric}_kde.png'
        )
    
    # Save results
    diag_df.to_csv(RESULTS / f'exp2_{index_name}_diagnostics.csv', index=False)
    print(f'\nExp2 diagnostics saved for {index_name}')
    return diag_df


if __name__ == '__main__':
    df = run_exp2('VIX')
    print('\nExperiment 2 complete.')
