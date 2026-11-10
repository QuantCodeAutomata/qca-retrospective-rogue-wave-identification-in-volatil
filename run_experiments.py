"""Offline-first reproducible entry point. Run --help for CSV and demo examples."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from numbers import Integral
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from data.data_loader import (load_config, load_daily_highs, prepare_daily_highs,
                              validate_daily_highs, series_digest)
from src.configuration import validate_config

ROOT = Path(__file__).resolve().parent


def demo_series(index_name, n=320):
    """Deterministic artificial signal solely for pipeline smoke testing."""
    rng = np.random.default_rng(20261020)
    t = np.arange(n, dtype=float)
    values = 18 + 2 * np.sin(t / 15) + 0.3 * rng.normal(size=n)
    values += 35 * np.exp(-0.5 * ((t - 150) / 8)**2)
    values += 55 * np.exp(-0.5 * ((t - 270) / 5)**2)
    series = validate_daily_highs(pd.Series(values, index=pd.bdate_range('2000-01-03', periods=n)), index_name)
    series.attrs.update({'source': 'deterministic_synthetic_smoke_test', 'is_synthetic': True,
                         'seed': 20261020, 'series_sha256': series_digest(series)})
    return series


def code_hashes():
    paths = set(ROOT.glob('*.py')) | set(ROOT.glob('requirements*.txt')) | set(ROOT.glob('constraints*.txt'))
    for directory in ('src', 'data', 'exp', 'configs', 'tests', 'scripts'):
        paths.update(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and p.suffix in {'.py', '.yaml', '.csv'})
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def _experiments(index_name, requested):
    realtime = {'VIX': 4, 'VXO': 5, 'VSTOXX': 6}[index_name]
    if isinstance(requested, str):
        if requested == 'all':
            return [1, 2, 3, realtime]
        try:
            requested = [int(value.strip()) for value in requested.split(',')]
        except ValueError as exc:
            raise ValueError('experiments must be all or comma-separated integers') from exc
    try:
        values = list(requested)
    except TypeError as exc:
        raise ValueError('experiments must be all, comma-separated integers or a sequence of integers') from exc
    if not values or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral)
                         or v not in (1, 2, 3, realtime) for v in values):
        raise ValueError(f'{index_name} supports experiments 1,2,3,{realtime}')
    return list(dict.fromkeys(int(v) for v in values))


def _write_manifest(path, manifest):
    """Replace one complete manifest, so interrupted writes do not truncate it."""
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                    allow_nan=False, default=str) + '\n', encoding='utf-8')
    temporary.replace(path)


def run_project(index_name, highs, config=None, experiments='all', output_dir=None, progress=True):
    """Public Python API with the same bounds, provenance and overwrite guard as CLI.

    Returns ``{'output_dir': Path, 'results': {experiment_number: result}}``.
    Inputs and configuration are copied; no experiment owns the output folder.
    """
    index_name = index_name.upper()
    cfg = validate_config(load_config(index_name) if config is None else config, index_name)
    selected = _experiments(index_name, experiments)
    highs = prepare_daily_highs(highs, index_name, cfg['sample_start'], cfg['sample_end'])
    highs.attrs.setdefault('source', 'programmatic_series')
    highs.attrs.setdefault('is_synthetic', False)
    highs.attrs.setdefault('index_identity', 'asserted_by_input_owner')
    realtime = {'VIX': 4, 'VXO': 5, 'VSTOXX': 6}[index_name]
    minimum = (cfg['window_L'] + cfg['block_len'] - 1 if realtime in selected
               else cfg['window_L'] + 1 if 3 in selected
               else cfg['window_L'] if 2 in selected else 4)
    if len(highs) < minimum:
        raise ValueError(f'selected experiments require at least {minimum} observations; got {len(highs)}')
    now = datetime.now(timezone.utc)
    tag = 'synthetic' if highs.attrs['is_synthetic'] else index_name.lower()
    output = (Path(output_dir).expanduser().resolve() if output_dir is not None else
              ROOT / 'results' / f'{tag}_{cfg["filter_mode"]}_{now:%Y%m%dT%H%M%S%fZ}')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('output directory is not empty; choose a new directory to preserve run provenance')
    packages = {name: importlib.metadata.version(name)
                for name in ('numpy', 'scipy', 'pandas', 'matplotlib', 'seaborn', 'PyYAML')}
    if highs.attrs['source'] == 'yahoo':
        packages['yfinance'] = importlib.metadata.version('yfinance')
    manifest = {'status': 'running', 'created_utc': now.isoformat(),
                'index': index_name, 'is_synthetic': bool(highs.attrs['is_synthetic']),
                'config': cfg, 'experiments': selected, 'input': dict(highs.attrs),
                'actual_start': str(highs.index[0].date()), 'actual_end': str(highs.index[-1].date()),
                'rows': len(highs), 'python': sys.version, 'platform': platform.platform(),
                'packages': packages, 'source_sha256': code_hashes(),
                'caveats': ['Exact author data snapshot, normalization and boundary details are unavailable.',
                            'Full-sample peak labels are retrospective and can change when endpoint changes.',
                            'Published thresholds are not recalibrated; no performance match is promised.']}
    if (highs.index.dayofweek >= 5).any():
        manifest['caveats'].append('Weekend rows detected: confirm these are actual index sessions, not inserted valuations.')
    if highs.attrs['is_synthetic']:
        manifest['caveats'].append('SYNTHETIC TEST ONLY: output is not evidence for any financial index.')
    initial_manifest = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False, default=str)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / 'run_metadata.json'
    # Claim even an existing empty directory exclusively before any output writes.
    with manifest_path.open('x', encoding='utf-8') as stream:
        stream.write(initial_manifest + '\n')
    context = {'index_name': index_name, 'highs': highs, 'config': cfg, 'output_dir': output}
    results = {}
    try:
        highs.rename('high').to_csv(output / 'input_highs.csv', date_format='%Y-%m-%d', float_format='%.17g')
        print(f'{index_name}: {len(highs)} sessions, {highs.index[0].date()} to {highs.index[-1].date()}')
        print(f'Output: {output}')
        for experiment in selected:
            if experiment == 1:
                from exp.exp1_rogue_wave_identification import run_exp1
                result = run_exp1(index_name, highs, cfg, output, context=context)
            elif experiment == 2:
                from exp.exp2_schrodinger_eigenanalysis import run_exp2
                result = run_exp2(index_name, highs, cfg, output, context=context)
            elif experiment == 3:
                from exp.exp3_eigenvalue_gradient import run_exp3
                result = run_exp3(index_name, highs, cfg, output, context=context)
            else:
                from exp.common import run_realtime_experiment
                result = run_realtime_experiment(index_name, experiment, highs, cfg, output,
                                                 progress, context=context)
            results[experiment] = result
        if cfg['paper_diagnostics']:
            from exp.common import descriptive_for
            from src.paper_diagnostics import run_paper_diagnostics
            results['paper_diagnostics'] = run_paper_diagnostics(
                index_name, highs, context.get('warnings'), cfg, output,
                descriptive_envelope=descriptive_for(highs, cfg, context)['envelope'])
        manifest['outputs_sha256'] = {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob('*')) if p.is_file() and p != manifest_path}
        manifest['status'] = 'completed'
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest_path, manifest)
    except BaseException as exc:
        manifest['status'] = 'failed'
        manifest['error'] = f'{type(exc).__name__}: {exc}'
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        _write_manifest(manifest_path, manifest)
        raise
    return {'output_dir': output, 'results': results}


def main(argv=None, *, default_index='VIX', default_experiments='all'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=str.upper, choices=['VIX', 'VXO', 'VSTOXX'], default=default_index)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--csv', type=Path, help='Real daily highs, with date/high columns by default')
    source.add_argument('--demo', action='store_true', help='Clearly labeled synthetic smoke test; never a replication result')
    source.add_argument('--source', choices=['yahoo'], help='Explicit optional download; fails instead of substituting synthetic data')
    parser.add_argument('--date-column', default='date')
    parser.add_argument('--high-column', default='high')
    parser.add_argument('--start', help='Inclusive first session date; default all supplied history')
    parser.add_argument('--end', help='Inclusive frozen final date; default all supplied history')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--filter-mode', choices=['spectral_peaks', 'all_bins'])
    parser.add_argument('--insample-end', help='OOS starts after this inclusive in-sample cutoff')
    parser.add_argument('--labels', choices=['own', 'paper', 'both'], default=None,
                        help='Evaluation catalogue (default own, or the value in config)')
    parser.add_argument('--baseline', choices=['rolling_max'], default=None,
                        help='Compare with the maximum of the same squared envelope')
    parser.add_argument('--paper-diagnostics', action='store_true', default=None,
                        help='Add article diagnostics; these do not change the warning algorithm')
    parser.add_argument('--experiments', default=default_experiments,
                        help='all or comma-separated numbers. Realtime:4=VIX,5=VXO,6=VSTOXX')
    parser.add_argument('--output', type=Path, help='New or empty output directory; existing runs are not overwritten')
    parser.add_argument('--quiet', action='store_true', help='Disable per100-prefix progress')
    args = parser.parse_args(argv)
    if not args.csv and not args.demo and args.source is None:
        parser.error('provide --csv PATH, --source yahoo, or --demo')
    try:
        cfg = load_config(args.index, args.config)
        for name in ('filter_mode', 'insample_end', 'labels', 'baseline', 'paper_diagnostics'):
            value = getattr(args, name)
            if value is not None:
                cfg[name] = value
        if args.start is not None:
            cfg['sample_start'] = args.start
        if args.end is not None:
            cfg['sample_end'] = args.end
        cfg = validate_config(cfg, args.index)
        selected = _experiments(args.index, args.experiments)
        highs = demo_series(args.index) if args.demo else load_daily_highs(
            args.index, csv_path=args.csv, source=args.source or 'csv', config=cfg,
            date_column=args.date_column, high_column=args.high_column, apply_bounds=False)
        return run_project(args.index, highs, cfg, selected, args.output, not args.quiet)['output_dir']
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
