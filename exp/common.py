"""Shared experiment computation inside a provenance-owning project run."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.signal_processing import process_series
from src.peak_detection import full_peak_analysis


def direct_run(index_name, experiment_number, highs, config, output_dir, progress=True):
    """Route public experiment functions through the same guarded runner as CLI."""
    from run_experiments import run_project
    run = run_project(index_name, highs, config=config, experiments=[experiment_number],
                      output_dir=output_dir, progress=progress)
    return run['results'][experiment_number]


def prepare(index_name, highs=None, config=None, output_dir=None, *, context=None):
    if context is None:
        raise ValueError('Experiments require a managed run; use run_project or run_expN')
    return context['config'], context['highs'], context['output_dir']


def envelope_for(highs, config, realtime=False):
    key = 'filter_percentile_realtime' if realtime else 'filter_percentile_descriptive'
    return process_series(highs.to_numpy(dtype=float), float(config[key]), config['filter_mode'])


def peaks_for(highs, envelope, config):
    return full_peak_analysis(highs.index, envelope,
                              threshold_lower=float(config['threshold_lower_extreme']),
                              threshold_major=float(config['threshold_major_rogue']))


def descriptive_for(highs, config, context):
    if 'descriptive' not in context:
        envelope = envelope_for(highs, config)
        peaks, swh = peaks_for(highs, envelope, config)
        context['descriptive'] = {'envelope': envelope, 'peaks': peaks, 'swh': swh}
    return context['descriptive']


def diagnostics_for(highs, config, context):
    if 'descriptive_eigenanalysis' not in context:
        from src.schrodinger import rolling_schrodinger_analysis
        context['descriptive_eigenanalysis'] = rolling_schrodinger_analysis(
            highs.index, descriptive_for(highs, config, context)['envelope'],
            window_L=config['window_L'], boundary_condition=config['boundary_condition'],
            delta_t=config['delta_t'])
    # Exp2 adds display bins; never let them mutate the common numeric result.
    return context['descriptive_eigenanalysis'].copy()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False, default=str) + '\n', encoding='utf-8')


def display_pct(value):
    return 'undefined (empty denominator)' if value is None else f'{value:.2f}%'


def save_evaluation(output, prefix, evaluated, provenance, catalog_metadata):
    for severity in ('major', 'lower'):
        evaluated['signals'][severity].to_csv(output / f'{prefix}_signals_{severity}.csv', index=False)
        evaluated['censored_signals'][severity].to_csv(
            output / f'{prefix}_signals_{severity}_endpoint_censored.csv', index=False)
        evaluated['events'][severity].to_csv(output / f'{prefix}_events_{severity}.csv', index=False)
    evaluated['episodes'].to_csv(output / f'{prefix}_episodes.csv', index=False)
    evaluated['horizons'].to_csv(output / f'{prefix}_horizon_sensitivity.csv', index=False)
    result = dict(evaluated['metrics'])
    result['diagnostics'] = evaluated['diagnostics']
    result['is_synthetic'] = bool(provenance.get('is_synthetic'))
    result['data_provenance'] = dict(provenance)
    result['catalog'] = catalog_metadata
    write_json(output / f'{prefix}_evaluation.json', result)
    return result


def run_realtime_experiment(index_name, experiment_number, highs=None, config=None,
                            output_dir=None, progress=True, *, context=None):
    if context is None:
        return direct_run(index_name, experiment_number, highs, config, output_dir, progress)
    from src.realtime_pipeline import run_realtime_simulation, WARNING_COLUMNS
    from src.evaluation import collapse_signal_runs
    from src.benchmark import evaluate_catalog, load_paper_catalog
    from src.plotting import figure_warning_indicator

    cfg, highs, output = prepare(index_name, highs, config, output_dir, context=context)
    envelope = envelope_for(highs, cfg, realtime=True)
    own_peaks, swh = peaks_for(highs, envelope, cfg)
    all_warnings = run_realtime_simulation(
        highs, percentile_threshold=cfg['filter_percentile_realtime'],
        window_L=cfg['window_L'], block_len=cfg['block_len'],
        threshold_grad_count=cfg['threshold_grad_count'], filter_mode=cfg['filter_mode'],
        boundary_condition=cfg['boundary_condition'], delta_t=cfg['delta_t'],
        progress=progress, baseline=cfg.get('baseline'))
    warnings = all_warnings[WARNING_COLUMNS].copy()
    context['warnings'] = warnings
    prefix = f'exp{experiment_number}_{index_name.lower()}'
    warnings.to_csv(output / f'{prefix}_warning_data.csv', index=False)
    own_peaks.to_csv(output / f'{prefix}_reference_peaks.csv', index=False)
    pd.Series(envelope, index=highs.index, name='retrospective_envelope').to_csv(
        output / f'{prefix}_reference_envelope.csv')
    catalogs = {}
    if cfg.get('labels', 'own') in {'own', 'both'}:
        catalogs['own'] = (own_peaks, {'source': 'full_sample_retrospective', 'swh': swh})
    if cfg.get('labels') in {'paper', 'both'}:
        catalogs['paper'] = load_paper_catalog(index_name, highs.index)
    scored = {}
    primary = 'own' if 'own' in catalogs else 'paper'
    for name, (peaks, metadata) in catalogs.items():
        evaluated = evaluate_catalog(warnings, peaks, highs.index, cfg)
        label_prefix = prefix if name == primary else f'{prefix}_{name}'
        scores = save_evaluation(output, label_prefix, evaluated, highs.attrs, metadata)
        scored[name] = {'catalog': metadata, **scores}
        peaks.to_csv(output / f'{prefix}_{name}_catalog.csv', index=False)

    metrics = {
        'index': index_name, 'experiment': experiment_number,
        'data_provenance': dict(highs.attrs),
        'protocol': {
            'primary_labels': primary,
            'reference_labels': ('fixed retrospective paper event catalog' if primary == 'paper'
                                 else 'computed full-sample retrospective event catalog'),
            'reference_use': 'evaluation only; NOT a causal model input',
            'reference_percentile': cfg['filter_percentile_realtime'], 'swh': swh,
            'filter_mode': cfg['filter_mode'],
            'signal_availability': 'after the daily High is finalized; event_date is explanatory only',
            'trading_day_calendar': 'actual observed session index',
            'first_eligible_signal_date': str(warnings['date'].iloc[0].date()),
            'boundary_condition': cfg['boundary_condition'],
            'amplitude_scale': 'raw index points; paper normalization unspecified',
            'thresholds': {k: cfg[k] for k in ('threshold_grad_count', 'threshold_warning',
                                              'detection_window_days', 'min_inter_peak_days', 'late_signal_days')},
            'right_edge_labels': 'final incomplete waves and endpoint prominences are unresolved',
        },
        **{k: scored[primary][k] for k in ('full_sample', 'after_warmup', 'endpoint_censored', 'out_of_sample')},
        'label_catalogs': scored,
        'interpretation': 'reimplementation under declared assumptions; not proof of exact replication or trading profitability',
    }
    first = collapse_signal_runs(pd.Series(warnings.W_i.to_numpy(), index=pd.DatetimeIndex(warnings.date)), cfg['threshold_warning'])
    if cfg.get('baseline'):
        control = all_warnings[['date'] + ['baseline_' + c for c in WARNING_COLUMNS if c != 'date']].copy()
        control.columns = WARNING_COLUMNS
        bp = prefix + '_baseline_rolling_max'
        control.to_csv(output / f'{bp}_warning_data.csv', index=False)
        baseline_scores = {}
        for name, (peaks, metadata) in catalogs.items():
            baseline_scores[name] = {'catalog': metadata, **save_evaluation(
                output, f'{bp}_{name}', evaluate_catalog(control, peaks, highs.index, cfg), highs.attrs, metadata)}
        bfirst = collapse_signal_runs(pd.Series(control.W_i.to_numpy(), index=pd.DatetimeIndex(control.date)), cfg['threshold_warning'])
        decisions = warnings.W_i.to_numpy() > cfg['threshold_warning']
        bdecisions = control.W_i.to_numpy() > cfg['threshold_warning']
        differences = pd.DataFrame({'date': warnings.date, 'qca_warning': warnings.W_i,
                                    'baseline_warning': control.W_i, 'qca_alarm': decisions,
                                    'baseline_alarm': bdecisions})
        differences.loc[decisions != bdecisions].to_csv(output / f'{bp}_decision_disagreements.csv', index=False)
        comparison = {'definition': 'maximum squared value of the SAME causal envelope on retained operator coordinates',
                      'is_synthetic': bool(highs.attrs.get('is_synthetic')), 'data_provenance': dict(highs.attrs),
                      'daily_decisions': len(warnings), 'disagreement_days': int(np.count_nonzero(decisions != bdecisions)),
                      'max_abs_W_difference': float(np.max(np.abs(warnings.W_i.to_numpy()-control.W_i.to_numpy()))),
                      'qca_only_episodes': first.difference(bfirst).strftime('%Y-%m-%d').tolist(),
                      'baseline_only_episodes': bfirst.difference(first).strftime('%Y-%m-%d').tolist(),
                      'label_catalogs': baseline_scores}
        write_json(output / f'{bp}_comparison.json', comparison)
        metrics['baseline'] = comparison
    write_json(output / f'{prefix}_metrics.json', metrics)
    for severity in ('major', 'lower'):
        m = metrics['full_sample'][severity]
        print(f'{index_name} {severity}: recall={display_pct(m["peaks_detected_pct"])}, '
              f'precision={display_pct(m["precision_pct"])}, '
              f'events={m["n_unique_detected_peaks"]}/{m["n_peaks"]}, signals={m["n_signals"]}')
    envelope_series = pd.Series(envelope, index=highs.index)
    for name, (peaks, _) in catalogs.items():
        display_peaks = peaks.copy()
        display_peaks['envelope_value'] = envelope_series.reindex(display_peaks.date).to_numpy()
        suffix = '' if name == primary else '_' + name
        title = index_name + f' [{name} event catalog]'
        if highs.attrs.get('is_synthetic'):
            title += ' [SYNTHETIC TEST]'
        figure_warning_indicator(highs, envelope_series, display_peaks,
                                 warnings, first, cfg['threshold_warning'], title,
                                 insample_end=cfg.get('insample_end'),
                                 save_path=output / f'{prefix}{suffix}_warning.png')
    return metrics
