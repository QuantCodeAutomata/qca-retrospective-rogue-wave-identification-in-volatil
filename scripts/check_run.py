"""Independently recount a completed run; never import production scoring code.

Usage: python scripts/check_run.py --run results/example --output receipt.json
Checks saved warning decisions, catalogs, ledgers, counts and provenance. It
does not recompute the envelope/eigenvalues or certify author-data equivalence.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATE_FIELDS = {'date', 'signal_date', 'associated_peak_date', 'peak_date',
               'first_signal_date', 'last_above_threshold_date', 'event_date',
               'date_max_grad'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value, field=''):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if field in DATE_FIELDS:
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


class Checks:
    def __init__(self):
        self.errors = []
        self.comparisons = 0
        self.hashes = Counter()
        self.catalogs = []

    def equal(self, actual, expected, location, field=''):
        self.comparisons += 1
        actual, expected = normalize(actual, field), normalize(expected, field)
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            same = math.isfinite(actual) and math.isfinite(expected) and math.isclose(
                actual, expected, rel_tol=1e-10, abs_tol=1e-10)
        else:
            same = actual == expected
        if not same:
            self.errors.append({'location': location, 'expected': expected, 'actual': actual})

    def mapping(self, actual, expected, location):
        for key, value in expected.items():
            if key not in actual:
                self.errors.append({'location': f'{location}.{key}', 'error': 'missing key'})
            elif isinstance(value, dict):
                self.mapping(actual[key], value, f'{location}.{key}')
            else:
                self.equal(actual[key], value, f'{location}.{key}')

    def ledger(self, path, expected, fields):
        # A ledger containing only the literal category "false" must not be
        # inferred as a boolean column by the CSV reader.
        actual = pd.read_csv(path, dtype={'classification': str})
        self.equal(len(actual), len(expected), f'{path.name}.rows')
        missing = set(fields) - set(actual.columns)
        if missing:
            self.errors.append({'location': path.name, 'error': f'missing columns {sorted(missing)}'})
            return
        for row, (saved, wanted) in enumerate(zip(actual.to_dict('records'), expected)):
            for field in fields:
                self.equal(saved[field], wanted[field], f'{path.name}[{row}].{field}', field)

    def file_hashes(self, base, manifest, kind):
        base = base.resolve()
        for relative, expected in manifest.items():
            path = (base / relative).resolve()
            if not path.is_relative_to(base):
                self.errors.append({'location': relative, 'error': 'hash manifest path escapes its root'})
                continue
            if not path.is_file():
                self.errors.append({'location': f'{kind}:{relative}', 'error': 'missing hashed file'})
                continue
            self.equal(digest(path), expected, f'{kind}:{relative}.sha256')
            self.hashes[kind] += 1


def episode_rows(warnings, threshold):
    """Build runs with a scalar state machine, including open final episodes."""
    episodes = []
    active = None
    rows = warnings.to_dict('records')
    for row in rows:
        date, value = pd.Timestamp(row['date']), float(row['W_i'])
        if not math.isfinite(value):
            raise ValueError('Nonfinite saved warning')
        if value > threshold:
            if active is None:
                active = {'signal_date': date, 'last_above_threshold_date': date,
                          'duration_observations': 0, 'open_at_end': False,
                          'max_warning': value}
            active['last_above_threshold_date'] = date
            active['duration_observations'] += 1
            active['max_warning'] = max(active['max_warning'], value)
        elif active is not None:
            episodes.append(active)
            active = None
    if active is not None:
        active['open_at_end'] = True
        episodes.append(active)
    return episodes


def classify(signals, peaks, calendar, severity, horizon, guard, late, censored=False):
    """Independent scalar classifier, using the declared observation calendar."""
    position = {date: i for i, date in enumerate(calendar)}
    extreme = sorted((position[pd.Timestamp(row.date)], row.severity)
                     for row in peaks.itertuples(index=False)
                     if row.severity in {'major', 'lower'})
    all_positions = [i for i, _ in extreme]
    targets = [i for i, kind in extreme if severity == 'lower' or kind == 'major']
    result = []
    for date in signals:
        s = position[date]
        a, t = bisect_right(all_positions, s), bisect_right(targets, s)
        previous = targets[t - 1] if t else None
        prior_any = all_positions[a - 1] if a else None
        next_target = targets[t] if t < len(targets) else None
        next_any = all_positions[a] if a < len(all_positions) else None
        target_in_horizon = next_target is not None and next_target <= s + horizon
        any_in_horizon = next_any is not None and next_any <= s + horizon
        association = None
        if previous is not None and previous >= s - late:
            kind, association = 'late', previous
        elif prior_any is not None and prior_any >= s - late:
            kind, association = 'low', prior_any
        elif target_in_horizon:
            association = next_target
            kind = 'recovery' if previous is not None and previous >= s - guard else 'detected'
        elif censored and s + horizon >= len(calendar):
            kind, association = 'censored', next_any if any_in_horizon else None
        elif any_in_horizon:
            kind, association = 'low', next_any
        else:
            kind = 'false'
        result.append({'signal_date': date, 'classification': kind,
                       'associated_peak_date': calendar[association] if association is not None else None,
                       'lead_trading_days': association - s if association is not None else None,
                       'days_since_previous_peak': s - previous if previous is not None else None})
    return result


def metric_counts(rows, peaks, severity, start=None, no_eligible=False):
    target = {pd.Timestamp(row.date) for row in peaks.itertuples(index=False)
              if row.severity == 'major' or severity == 'lower' and row.severity == 'lower'}
    if start is not None:
        start = pd.Timestamp(start)
        target = {date for date in target if date >= start}
        rows = [row for row in rows if row['signal_date'] >= start]
    if no_eligible:
        target = set()
    counts = Counter(row['classification'] for row in rows)
    useful = [row for row in rows if row['classification'] == 'detected']
    detected = {row['associated_peak_date'] for row in useful} & target
    evaluated = len(rows) - counts['censored']
    pct = lambda n, d: 100.0 * n / d if d else None
    return {'peaks_detected_pct': pct(len(detected), len(target)),
            'false_signal_pct': pct(counts['false'], evaluated),
            'precision_pct': pct(len(useful), evaluated),
            'precision_excl_late_pct': pct(len(useful), evaluated - counts['late']),
            'n_peaks': len(target), 'n_signals': len(rows), 'n_evaluated_signals': evaluated,
            'n_detected': len(useful), 'n_unique_detected_peaks': len(detected),
            'n_false': counts['false'], 'n_late': counts['late'], 'n_low': counts['low'],
            'n_recovery': counts['recovery'], 'n_censored': counts['censored']}


def event_rows(rows, peaks, severity):
    result = []
    for event in peaks.sort_values('date').itertuples(index=False):
        if event.severity not in ({'major'} if severity == 'major' else {'major', 'lower'}):
            continue
        date = pd.Timestamp(event.date)
        useful = sorted((row for row in rows if row['classification'] == 'detected'
                         and row['associated_peak_date'] == date), key=lambda row: row['signal_date'])
        result.append({'peak_date': date, 'severity': event.severity, 'detected': bool(useful),
                       'n_useful_episodes': len(useful),
                       'first_signal_date': useful[0]['signal_date'] if useful else None,
                       'lead_trading_days': useful[0]['lead_trading_days'] if useful else None})
    return result


def distribution(values):
    return {'count': len(values), 'min': min(values) if values else None,
            'median': float(np.median(values)) if values else None,
            'max': max(values) if values else None}


def check_catalog(checks, run, prefix, scores, warnings, peaks, calendar, cfg):
    location = prefix
    episodes = episode_rows(warnings, cfg['threshold_warning'])
    signals = [row['signal_date'] for row in episodes]
    checks.ledger(run / f'{prefix}_episodes.csv', episodes,
                  ['signal_date', 'last_above_threshold_date', 'duration_observations', 'open_at_end', 'max_warning'])
    options = dict(horizon=cfg['detection_window_days'], guard=cfg['min_inter_peak_days'],
                   late=cfg['late_signal_days'])
    expected_scores, horizon_rows, episode_leads, event_leads = {}, [], {}, {}
    for severity in ('major', 'lower'):
        rows = classify(signals, peaks, calendar, severity, **options)
        censored = classify(signals, peaks, calendar, severity, censored=True, **options)
        for suffix, ledger in [('', rows), ('_endpoint_censored', censored)]:
            checks.ledger(run / f'{prefix}_signals_{severity}{suffix}.csv', ledger,
                          ['signal_date', 'classification', 'associated_peak_date',
                           'lead_trading_days', 'days_since_previous_peak'])
        events = event_rows(rows, peaks, severity)
        checks.ledger(run / f'{prefix}_events_{severity}.csv', events,
                      ['peak_date', 'severity', 'detected', 'n_useful_episodes',
                       'first_signal_date', 'lead_trading_days'])
        for scope, ledger, kwargs in [
                ('full_sample', rows, {}),
                ('after_warmup', rows, {'start': warnings.date.iloc[0] if len(warnings) else None,
                                       'no_eligible': not len(warnings)}),
                ('endpoint_censored', censored, {})]:
            expected = metric_counts(ledger, peaks, severity, **kwargs)
            checks.mapping(scores[scope][severity], expected, f'{location}.{scope}.{severity}')
            expected_scores.setdefault(scope, {})[severity] = expected
        if cfg.get('insample_end'):
            start = pd.Timestamp(cfg['insample_end']) + pd.Timedelta(days=1)
            expected = metric_counts(rows, peaks, severity, start=start)
            checks.mapping(scores['out_of_sample']['metrics'][severity], expected,
                           f'{location}.out_of_sample.{severity}')
        for horizon in (20, 60, 120, 240):
            ledger = classify(signals, peaks, calendar, severity, **{**options, 'horizon': horizon})
            horizon_rows.append({'horizon_observations': horizon, 'severity': severity,
                                 **metric_counts(ledger, peaks, severity)})
        episode_leads[severity] = distribution([r['lead_trading_days'] for r in rows if r['classification'] == 'detected'])
        event_leads[severity] = distribution([r['lead_trading_days'] for r in events if r['detected']])
    checks.equal(scores['out_of_sample']['status'], 'configured' if cfg.get('insample_end') else 'not_configured',
                 f'{location}.out_of_sample.status')
    if not cfg.get('insample_end'):
        checks.equal(scores['out_of_sample']['metrics'], {}, f'{location}.out_of_sample.metrics')
    checks.ledger(run / f'{prefix}_horizon_sensitivity.csv', horizon_rows, list(horizon_rows[0]))
    days_above = sum(row['duration_observations'] for row in episodes)
    diagnostics = {'eligible_warning_days': len(warnings), 'days_above_threshold': days_above,
                   'days_above_threshold_pct': 100.0 * days_above / len(warnings) if len(warnings) else None,
                   'alarm_fraction': days_above / len(warnings) if len(warnings) else None,
                   'n_episodes': len(episodes), 'open_episodes_at_end': sum(r['open_at_end'] for r in episodes),
                   'episode_duration_observations': distribution([r['duration_observations'] for r in episodes]),
                   'useful_episode_lead_observations': episode_leads,
                   'detected_event_first_lead_observations': event_leads}
    checks.mapping(scores['diagnostics'], diagnostics, f'{location}.diagnostics')
    evaluation = json.loads((run / f'{prefix}_evaluation.json').read_text())
    for key in ('full_sample', 'after_warmup', 'endpoint_censored', 'out_of_sample', 'diagnostics'):
        checks.mapping(evaluation[key], scores[key], f'{prefix}_evaluation.json.{key}')
    checks.catalogs.append({'prefix': prefix, 'warning_days': len(warnings),
                            'episodes': len(episodes), 'events': len(peaks)})


def checked_warnings(checks, path, calendar, cfg):
    warnings = pd.read_csv(path, parse_dates=['date', 'event_date', 'date_max_grad'])
    dates = pd.DatetimeIndex(warnings.date)
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError(f'Invalid warning calendar in {path.name}')
    start = cfg['window_L'] + cfg['block_len'] - 2
    checks.equal(dates.strftime('%Y-%m-%d').tolist(), calendar[start:].strftime('%Y-%m-%d').tolist(),
                 f'{path.name}.eligible_dates')
    for i, row in enumerate(warnings.itertuples(index=False)):
        checks.equal(row.W_i, row.M_i * row.C_i if row.C_i else 0., f'{path.name}[{i}].W=M*C')
        if not float(row.C_i).is_integer() or not 0 <= row.C_i <= cfg['block_len']:
            checks.errors.append({'location': f'{path.name}[{i}].C_i', 'error': 'count outside valid block'})
        offset = row.argmax_offset
        if not float(offset).is_integer() or not 0 <= offset < cfg['block_len']:
            checks.errors.append({'location': f'{path.name}[{i}].argmax_offset', 'error': 'offset outside valid block'})
        else:
            position = calendar.get_loc(pd.Timestamp(row.date)) - cfg['block_len'] + 1 + int(offset)
            checks.equal(row.event_date, calendar[position], f'{path.name}[{i}].event_date', 'event_date')
            checks.equal(row.date_max_grad, row.event_date, f'{path.name}[{i}].date_max_grad', 'date_max_grad')
    return warnings


def validate_run(run):
    run = Path(run).resolve()
    checks = Checks()
    receipt = {'run': str(run), 'checked_utc': datetime.now(timezone.utc).isoformat(),
               'validator_sha256': digest(Path(__file__)),
               'scope': 'Independent warning-ledger arithmetic, event scoring and hashes; no production scorer imports; no envelope/eigenvalue recomputation'}
    try:
        manifest_path = run / 'run_metadata.json'
        manifest = json.loads(manifest_path.read_text())
        receipt['run_manifest_sha256'] = digest(manifest_path)
        checks.equal(manifest['status'], 'completed', 'run_metadata.status')
        cfg = manifest['config']
        highs = pd.read_csv(run / 'input_highs.csv', float_precision='round_trip')
        calendar = pd.DatetimeIndex(pd.to_datetime(highs.iloc[:, 0]))
        if calendar.hasnans or calendar.has_duplicates or not calendar.is_monotonic_increasing:
            raise ValueError('Input calendar is not sorted and unique')
        if not np.isfinite(highs.iloc[:, 1].to_numpy(dtype=float)).all() or (highs.iloc[:, 1] <= 0).any():
            raise ValueError('Saved highs are not finite positive values')
        checks.equal(len(highs), manifest['rows'], 'run_metadata.rows')
        checks.equal(str(calendar[0].date()), manifest['actual_start'], 'run_metadata.actual_start')
        checks.equal(str(calendar[-1].date()), manifest['actual_end'], 'run_metadata.actual_end')
        checks.equal(digest(run / 'input_highs.csv'), manifest['input']['series_sha256'], 'input.series_sha256')
        checks.file_hashes(run, manifest['outputs_sha256'], 'outputs')
        checks.file_hashes(ROOT, manifest['source_sha256'], 'current_source')
        realtime_files = []
        for experiment in manifest['experiments']:
            if experiment not in (4, 5, 6):
                continue
            prefix = f'exp{experiment}_{manifest["index"].lower()}'
            path = run / f'{prefix}_metrics.json'
            realtime_files.append(path.name)
            metrics = json.loads(path.read_text())
            checks.equal(metrics['index'], manifest['index'], f'{path.name}.index')
            checks.equal(metrics['experiment'], experiment, f'{path.name}.experiment')
            checks.mapping(metrics['protocol']['thresholds'], {
                name: cfg[name] for name in ('threshold_grad_count', 'threshold_warning',
                                            'detection_window_days', 'min_inter_peak_days', 'late_signal_days')
            }, f'{path.name}.protocol.thresholds')
            warnings = checked_warnings(checks, run / f'{prefix}_warning_data.csv', calendar, cfg)
            primary = metrics['protocol']['primary_labels']
            for label, scores in metrics['label_catalogs'].items():
                peaks = pd.read_csv(run / f'{prefix}_{label}_catalog.csv', parse_dates=['date'])
                if peaks.date.duplicated().any() or peaks.date.isna().any() or not peaks.severity.isin(['normal', 'lower', 'major']).all():
                    raise ValueError(f'Invalid {label} catalog')
                if (calendar.get_indexer(peaks.date) < 0).any():
                    raise ValueError(f'{label} event outside observed calendar')
                label_prefix = prefix if label == primary else f'{prefix}_{label}'
                check_catalog(checks, run, label_prefix, scores, warnings, peaks, calendar, cfg)
                if label == primary:
                    for key in ('full_sample', 'after_warmup', 'endpoint_censored', 'out_of_sample'):
                        checks.mapping(metrics[key], scores[key], f'{path.name}.{key}')
                if label == 'paper':
                    source = (ROOT / scores['catalog']['source_file']).resolve()
                    if not source.is_relative_to(ROOT):
                        raise ValueError('Paper source path escapes the project')
                    checks.equal(digest(source), scores['catalog']['source_sha256'], 'paper_catalog.sha256')
                    table = pd.read_csv(source, parse_dates=['date'])
                    reference = table[table.peak_lower.fillna(0).eq(1)]
                    in_range = reference.date.between(calendar[0], calendar[-1])
                    expected = [{'date': r.date, 'severity': 'major' if r.peak_major == 1 else 'lower'}
                                for r in reference[in_range].sort_values('date').itertuples(index=False)]
                    checks.ledger(run / f'{prefix}_{label}_catalog.csv', expected, ['date', 'severity'])
                    checks.mapping(scores['catalog'], {
                        'total_events': len(reference), 'covered_events': int(in_range.sum()),
                        'coverage_complete': bool(in_range.all()),
                        'covered_major_events': sum(r['severity'] == 'major' for r in expected),
                        'covered_lower_events': sum(r['severity'] == 'lower' for r in expected),
                        'missing_in_range_dates': [],
                        'out_of_range_events': [{'date': r.date.date().isoformat(),
                                                'severity': 'major' if r.peak_major == 1 else 'lower'}
                                               for r in reference[~in_range].sort_values('date').itertuples(index=False)]
                    }, f'{prefix}.paper_catalog_coverage')
            if 'baseline' in metrics:
                bp = prefix + '_baseline_rolling_max'
                control = checked_warnings(checks, run / f'{bp}_warning_data.csv', calendar, cfg)
                baseline = metrics['baseline']
                for label, scores in baseline['label_catalogs'].items():
                    peaks = pd.read_csv(run / f'{prefix}_{label}_catalog.csv', parse_dates=['date'])
                    check_catalog(checks, run, f'{bp}_{label}', scores, control, peaks, calendar, cfg)
                alarms = warnings.W_i.to_numpy() > cfg['threshold_warning']
                other = control.W_i.to_numpy() > cfg['threshold_warning']
                first = {r['signal_date'] for r in episode_rows(warnings, cfg['threshold_warning'])}
                second = {r['signal_date'] for r in episode_rows(control, cfg['threshold_warning'])}
                expected = {'daily_decisions': len(warnings),
                            'disagreement_days': int(np.count_nonzero(alarms != other)),
                            'max_abs_W_difference': float(np.max(np.abs(warnings.W_i.to_numpy() - control.W_i.to_numpy()))),
                            'qca_only_episodes': [d.date().isoformat() for d in sorted(first - second)],
                            'baseline_only_episodes': [d.date().isoformat() for d in sorted(second - first)]}
                checks.mapping(baseline, expected, f'{path.name}.baseline')
                comparison = json.loads((run / f'{bp}_comparison.json').read_text())
                checks.mapping(comparison, baseline, f'{bp}_comparison.json')
                disagreements = []
                for i in np.flatnonzero(alarms != other):
                    disagreements.append({'date': warnings.date.iloc[i], 'qca_warning': warnings.W_i.iloc[i],
                                          'baseline_warning': control.W_i.iloc[i], 'qca_alarm': bool(alarms[i]),
                                          'baseline_alarm': bool(other[i])})
                checks.ledger(run / f'{bp}_decision_disagreements.csv', disagreements,
                              ['date', 'qca_warning', 'baseline_warning', 'qca_alarm', 'baseline_alarm'])
        if not realtime_files:
            raise ValueError('No realtime experiment in this run; ledger validation is not applicable')
        receipt['realtime_metrics_files'] = realtime_files
    except Exception as exc:
        checks.errors.append({'location': 'validation', 'error': f'{type(exc).__name__}: {exc}'})
    receipt.update({'passed': not checks.errors, 'comparisons': checks.comparisons,
                    'hashes_checked': dict(checks.hashes), 'catalogs_checked': checks.catalogs,
                    'errors': checks.errors})
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='New JSON receipt path; otherwise print the receipt')
    args = parser.parse_args(argv)
    receipt = validate_run(args.run)
    payload = json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False, default=str) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(payload)
        print(json.dumps({'passed': receipt['passed'], 'comparisons': receipt['comparisons'],
                          'errors': len(receipt['errors']), 'receipt': str(args.output)}))
    else:
        print(payload, end='')
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
