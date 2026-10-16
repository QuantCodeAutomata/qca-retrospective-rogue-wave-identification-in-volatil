"""
Exp 3: Retrospective minimum-eigenvalue-gradient analysis.

Computes rolling |lambda_min|, its numerical gradient (numpy.gradient),
and compares with gradient of squared envelope.
VIX illustrative cutoff: 74.
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
from src.peak_detection import full_peak_analysis
from src.schrodinger import rolling_schrodinger_analysis
from src.diagnostics import (
    compute_gradient_series, compute_envelope_gradient, assign_days_to_next_peak
)
from src.plotting import figure3_style_scatter

RESULTS = Path('results')
RESULTS.mkdir(exist_ok=True)


def run_exp3(index_name: str = 'VIX') -> pd.DataFrame:
    print(f'\n=== Experiment 3: Eigenvalue Gradient Analysis ({index_name}) ===')
    cfg = load_config(index_name)
    highs = load_daily_highs(index_name)
    x = highs.values.astype(float)
    dates = highs.index
    
    # Process with 95% (realtime-aligned)
    pct = float(cfg.get('filter_percentile_realtime', 95.0))
    print(f'Processing envelope ({pct}% threshold)...')
    envelope = process_series(x, percentile_threshold=pct)
    
    # Ex post peak labels
    peak_df, swh = full_peak_analysis(dates, envelope)
    major_peaks = peak_df[peak_df['severity'] == 'major']
    major_peak_dates = pd.DatetimeIndex(major_peaks['date'])
    print(f'SWH={swh:.4f}, Major peaks: {len(major_peaks)}')
    
    # Rolling Schrodinger -> lambda_min series
    window_L = int(cfg.get('window_L', 80))
    print(f'Running rolling Schrodinger (L={window_L})...')
    diag_df = rolling_schrodinger_analysis(dates, envelope, window_L=window_L)
    lambda_series = pd.Series(
        diag_df['abs_lambda_min'].values,
        index=pd.DatetimeIndex(diag_df['date']),
        name='abs_lambda_min'
    )
    
    # Gradient of |lambda_min|
    grad_lambda = compute_gradient_series(lambda_series)
    
    # Gradient of squared envelope for comparison
    grad_sq_env = compute_envelope_gradient(envelope, dates, window_L=window_L)
    
    # Days to next peak
    days_series = assign_days_to_next_peak(lambda_series.index, major_peak_dates)
    
    # Combined DataFrame
    combined = pd.DataFrame({
        'grad_lambda': grad_lambda,
        'grad_sq_env': grad_sq_env,
        'days_to_next_peak': days_series,
    }).dropna(subset=['days_to_next_peak'])
    
    print(f'\nGradient stats: max={grad_lambda.max():.2f}, median={grad_lambda.median():.2f}')
    print(f'High gradient events (>74): {(grad_lambda > 74).sum()} days')
    
    # Plot: eigenvalue gradient vs days to next peak
    grad_cutoff = 74.0 if index_name == 'VIX' else None
    figure3_style_scatter(
        grad_series=grad_lambda,
        days_to_peak=days_series,
        index_name=index_name,
        gradient_cutoff=grad_cutoff,
        save_path=RESULTS / f'exp3_{index_name}_grad_vs_days.png'
    )
    
    # Comparison plot
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    axes[0].plot(grad_lambda.index, grad_lambda.values, color='blue', lw=0.8, label='|lambda_min| gradient')
    if grad_cutoff:
        axes[0].axhline(grad_cutoff, color='red', linestyle='--', label=f'Cutoff={grad_cutoff}')
    for pk in major_peak_dates:
        axes[0].axvline(pk, color='red', alpha=0.4, lw=0.8)
    axes[0].set_ylabel('Gradient')
    axes[0].set_title(f'{index_name}: |lambda_min| Gradient (vs Major Peaks)')
    axes[0].legend(fontsize=7)
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(grad_sq_env.index, grad_sq_env.values, color='orange', lw=0.8, label='|psi|^2 gradient')
    for pk in major_peak_dates:
        axes[1].axvline(pk, color='red', alpha=0.4, lw=0.8)
    axes[1].set_ylabel('Gradient')
    axes[1].set_xlabel('Date')
    axes[1].set_title(f'{index_name}: Squared-Envelope Gradient (comparison)')
    axes[1].legend(fontsize=7)
    axes[1].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULTS / f'exp3_{index_name}_gradient_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    combined.to_csv(RESULTS / f'exp3_{index_name}_gradient_data.csv')
    print(f'Experiment 3 complete for {index_name}')
    return combined


if __name__ == '__main__':
    df = run_exp3('VIX')
    print('\nExperiment 3 complete.')
