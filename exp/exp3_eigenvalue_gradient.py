"""Exp3: all Figure 3 comparisons, explicitly retrospective (92.5%)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from exp.common import prepare, descriptive_for, diagnostics_for, direct_run, write_json
from src.diagnostics import compute_gradient_series, compute_envelope_gradient, assign_days_to_next_peak
from src.plotting import figure3_style_scatter, figure3_full_comparison


def run_exp3(index_name='VIX', highs=None, config=None, output_dir=None, *, context=None):
    if context is None:
        return direct_run(index_name, 3, highs, config, output_dir)
    cfg, highs, output = prepare(index_name, highs, config, output_dir, context=context)
    cached = descriptive_for(highs, cfg, context)
    envelope, peaks = cached['envelope'], cached['peaks']
    peak_dates = pd.DatetimeIndex(peaks.loc[peaks['severity'] == 'major', 'date'])
    diag = diagnostics_for(highs, cfg, context)
    if len(diag) < 2:
        raise ValueError('At least two valid rolling windows are required for a gradient')
    lam = pd.Series(diag['abs_lambda_min'].to_numpy(), index=pd.DatetimeIndex(diag['date']))
    grad = compute_gradient_series(lam)
    grad_env = compute_envelope_gradient(envelope, highs.index, cfg['window_L'])
    days = assign_days_to_next_peak(lam.index, peak_dates)
    aligned_env = pd.Series(envelope, index=highs.index).reindex(lam.index)
    combined = pd.DataFrame({'grad_lambda': grad, 'grad_sq_env': grad_env,
                             'days_to_next_peak': days, 'raw_high': highs.reindex(lam.index),
                             'envelope': aligned_env, 'negative_potential': aligned_env ** 2,
                             'abs_lambda_min': lam})
    combined.to_csv(output / f'exp3_{index_name}_gradient_data.csv')
    cutoff = 74.0 if index_name == 'VIX' else None
    title = index_name + (' [SYNTHETIC TEST]' if highs.attrs.get('is_synthetic') else '')
    figure3_style_scatter(grad, days, title, cutoff, output / f'exp3_{index_name}_grad_vs_days.png')
    figure3_full_comparison(combined, title, cutoff, output / f'exp3_{index_name}_gradient_comparison.png')
    write_json(output / f'exp3_{index_name}_summary.json',
               {'max_signed_gradient': float(grad.max()), 'days_above_74': int((grad > 74).sum()),
                'fft_percentile': cfg['filter_percentile_descriptive'],
                'figure_panels': ['3a', '3b', '3c', '3d'],
                'display_scale': 'raw index units and squared units on explicitly separate axes',
                'interpretation': 'descriptive only; cutoff74 is not a validated realtime threshold'})
    return combined


if __name__ == '__main__':
    from run_experiments import main
    main(default_experiments='3')
