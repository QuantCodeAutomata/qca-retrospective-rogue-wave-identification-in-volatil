"""Exp1: full-sample descriptive envelope and prominence labels (92.5%)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from exp.common import prepare, descriptive_for, direct_run, write_json
from src.peak_detection import full_peak_analysis
from src.plotting import figure1_style, histogram_raw_peaks, histogram_prominences


def run_exp1(index_name='VIX', highs=None, config=None, output_dir=None, *, context=None):
    if context is None:
        return direct_run(index_name, 1, highs, config, output_dir)
    cfg, highs, output = prepare(index_name, highs, config, output_dir, context=context)
    cached = descriptive_for(highs, cfg, context)
    envelope, peak_df, swh = cached['envelope'], cached['peaks'], cached['swh']
    raw_peaks, raw_swh = full_peak_analysis(highs.index, highs.to_numpy(),
        threshold_lower=cfg['threshold_lower_extreme'], threshold_major=cfg['threshold_major_rogue'])
    raw_peaks.rename(columns={'envelope_value': 'raw_high'}).to_csv(output / f'exp1_{index_name}_raw_peaks.csv', index=False)
    title = index_name + (' [SYNTHETIC TEST]' if highs.attrs.get('is_synthetic') else '')
    figure1_style(highs, pd.Series(envelope, index=highs.index), peak_df, title,
                  output / f'exp1_{index_name}_envelope_overlay.png', raw_peak_df=raw_peaks)
    histogram_raw_peaks(highs, title, output / f'exp1_{index_name}_histogram_raw.png')
    histogram_prominences(peak_df, swh, title, output / f'exp1_{index_name}_histogram_prominences.png')
    peak_df.to_csv(output / f'exp1_{index_name}_peaks.csv', index=False)
    pd.Series(envelope, index=highs.index, name='retrospective_envelope').to_csv(
        output / f'exp1_{index_name}_envelope.csv')
    result = {'index': index_name, 'swh': swh,
              'n_major': int((peak_df['severity'] == 'major').sum()),
              'n_lower': int((peak_df['severity'] == 'lower').sum()),
              'n_all_peaks': len(peak_df), 'n_raw_peaks': len(raw_peaks),
              'raw_swh': raw_swh,
              'n_raw_major': int((raw_peaks.severity == 'major').sum()),
              'n_raw_lower': int((raw_peaks.severity == 'lower').sum()),
              'peak_count_reduction_pct': 100.0 * (1 - len(peak_df) / len(raw_peaks)) if len(raw_peaks) else None,
              'fft_percentile': float(cfg['filter_percentile_descriptive']),
              'data_provenance': dict(highs.attrs),
              'interpretation': 'retrospective descriptive analysis; no predictive performance is measured'}
    write_json(output / f'exp1_{index_name}_metrics.json', result)
    print(f'{index_name}: {len(peak_df)} envelope peaks; SWH={swh:.4f}')
    return result


if __name__ == '__main__':
    from run_experiments import main
    main(default_experiments='1')
