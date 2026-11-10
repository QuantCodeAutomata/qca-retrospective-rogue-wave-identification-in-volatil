"""Exp2: retrospective localization diagnostics, never a forecasting backtest."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from exp.common import prepare, descriptive_for, diagnostics_for, direct_run, write_json
from src.diagnostics import assign_days_to_next_peak, bin_by_days_to_peak
from src.plotting import figure2_style_density


def run_exp2(index_name='VIX', highs=None, config=None, output_dir=None, *, context=None):
    if context is None:
        return direct_run(index_name, 2, highs, config, output_dir)
    cfg, highs, output = prepare(index_name, highs, config, output_dir, context=context)
    peaks = descriptive_for(highs, cfg, context)['peaks']
    major_dates = pd.DatetimeIndex(peaks.loc[peaks['severity'] == 'major', 'date'])
    diag = diagnostics_for(highs, cfg, context)
    if diag.empty:
        raise ValueError('Not enough observations for an eigenanalysis window')
    days = assign_days_to_next_peak(pd.DatetimeIndex(diag['date']), major_dates)
    diag['days_to_next_peak'] = days.to_numpy()
    diag['bin_label'] = bin_by_days_to_peak(days).to_numpy()
    # Show physical trading-day units and the scale-free fraction explicitly.
    window_span = (int(cfg['window_L']) - 1) * float(cfg['delta_t'])
    diag['loc_distance_fraction_of_window'] = diag['loc_distance'] / window_span
    diag['width_fraction_of_window'] = diag['width'] / window_span
    diag.to_csv(output / f'exp2_{index_name}_diagnostics.csv', index=False)
    summary = []
    title = index_name + (' [SYNTHETIC TEST]' if highs.attrs.get('is_synthetic') else '')
    for metric in ['width', 'loc_distance', 'skewness', 'kurtosis']:
        figure2_style_density(diag, metric, title, output / f'exp2_{index_name}_{metric}_kde.png')
        for label in ['0-5', '5-30', '>30']:
            values = diag.loc[diag['bin_label'] == label, metric].dropna()
            summary.append({'metric': metric, 'bin': label, 'n': len(values),
                            'mean': float(values.mean()) if len(values) else None,
                            'median': float(values.median()) if len(values) else None})
    write_json(output / f'exp2_{index_name}_summary.json',
               {'index': index_name, 'statistics': summary,
                'unassigned_windows': int(diag['bin_label'].isna().sum()),
                'interpretation': 'full-series envelope and future peak labels; descriptive only'})
    return diag


if __name__ == '__main__':
    from run_experiments import main
    main(default_experiments='2')
