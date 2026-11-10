"""Inspectable event scoring and controls for the paper-replication workflow.

The bundled catalogs are transcriptions of the paper's retrospective events,
not prospective ground truth. This module never changes warning timestamps,
fits thresholds, or fills missing market sessions.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation import (classify_first_signals, collapse_signal_runs,
                            compute_detection_metrics)


CATALOG_DIRECTORY = Path(__file__).resolve().parents[1] / 'verification' / 'source_evidence'
HORIZONS = (20, 60, 120, 240)
EPISODE_COLUMNS = ['signal_date', 'last_above_threshold_date',
                   'duration_observations', 'open_at_end', 'max_warning']
EVENT_COLUMNS = ['peak_date', 'severity', 'detected', 'n_useful_episodes',
                 'first_signal_date', 'lead_trading_days']


def _calendar(dates):
    calendar = pd.DatetimeIndex(dates)
    if calendar.hasnans or calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError('calendar must be sorted, unique and contain no NaT')
    return calendar


def _peaks(peak_df, calendar):
    if not {'date', 'severity'}.issubset(peak_df.columns):
        raise ValueError('peak catalog must contain date and severity')
    result = peak_df.copy()
    result['date'] = pd.to_datetime(result['date'])
    if result['date'].isna().any() or result['date'].duplicated().any():
        raise ValueError('peak dates must be nonmissing and unique')
    if not result['severity'].isin(['normal', 'lower', 'major']).all():
        raise ValueError('peak severity must be normal, lower or major')
    if (calendar.get_indexer(result['date']) < 0).any():
        raise ValueError('Every catalog peak must lie on the supplied calendar')
    return result.sort_values('date').reset_index(drop=True)


def load_paper_catalog(index_name, trading_dates):
    """Load S1/S2/S3 events, reporting coverage and rejecting absent sessions.

    Events outside the supplied date bounds are recorded as uncovered, not
    silently moved onto the closest session. An in-range missing event date
    is an error. The returned hash is of the exact bundled source CSV.
    """
    index = str(index_name).upper()
    if index not in ('VIX', 'VXO', 'VSTOXX'):
        raise ValueError('Paper catalogs are available for VIX, VXO and VSTOXX')
    calendar = _calendar(trading_dates)
    path = CATALOG_DIRECTORY / f'paper_{index}_supplement_table.csv'
    source_bytes = path.read_bytes()
    source = pd.read_csv(path, parse_dates=['date'])
    required = {'date', 'peak_lower', 'peak_major'}
    if not required.issubset(source.columns):
        raise ValueError(f'Incomplete paper catalog: {path.name}')
    events = source.loc[source['peak_lower'].fillna(0).eq(1), ['date', 'peak_major']].copy()
    events['severity'] = np.where(events.pop('peak_major').fillna(0).eq(1), 'major', 'lower')
    events = events.sort_values('date').reset_index(drop=True)
    if events['date'].isna().any() or events['date'].duplicated().any():
        raise ValueError(f'Invalid paper event dates: {path.name}')
    if len(calendar):
        in_range = events['date'].between(calendar[0], calendar[-1])
    else:
        in_range = pd.Series(False, index=events.index)
    covered = events.loc[in_range].copy().reset_index(drop=True)
    missing = covered.loc[calendar.get_indexer(covered['date']) < 0, 'date']
    if len(missing):
        dates = ', '.join(missing.dt.strftime('%Y-%m-%d'))
        raise ValueError(f'{index} paper event dates missing within supplied calendar: {dates}')
    outside = events.loc[~in_range]
    metadata = {
        'index': index,
        'catalog': 'paper_supplementary_events',
        'source_file': f'verification/source_evidence/{path.name}',
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'paper': 'arXiv:2606.31475v4',
        'supplementary_table': {'VIX': 'S1', 'VXO': 'S2', 'VSTOXX': 'S3'}[index],
        'reference_kind': 'fixed retrospective paper catalog; not independent prospective labels',
        'calendar_start': calendar[0].date().isoformat() if len(calendar) else None,
        'calendar_end': calendar[-1].date().isoformat() if len(calendar) else None,
        'total_events': len(events),
        'covered_events': len(covered),
        'covered_major_events': int(covered['severity'].eq('major').sum()),
        'covered_lower_events': int(covered['severity'].eq('lower').sum()),
        'coverage_complete': len(outside) == 0,
        'out_of_range_events': [
            {'date': row.date.date().isoformat(), 'severity': row.severity}
            for row in outside.itertuples(index=False)
        ],
        'missing_in_range_dates': [],
    }
    return covered, metadata


def _warning_series(warnings, calendar):
    if not {'date', 'W_i'}.issubset(warnings.columns):
        raise ValueError('warnings must contain date and W_i')
    dates = _calendar(warnings['date'])
    positions = calendar.get_indexer(dates)
    if (positions < 0).any():
        raise ValueError('Every warning date must lie on the supplied calendar')
    if len(positions) > 1 and not np.all(np.diff(positions) == 1):
        raise ValueError('Warning rows must cover consecutive observed sessions')
    values = warnings['W_i'].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Warnings must be finite')
    return pd.Series(values, index=dates, name='W_i')


def _episodes(warnings, threshold):
    above = warnings.to_numpy() > threshold
    starts = np.flatnonzero(above & ~np.r_[False, above[:-1]]) if len(above) else []
    ends = np.flatnonzero(above & ~np.r_[above[1:], False]) if len(above) else []
    records = []
    for start, end in zip(starts, ends):
        records.append({
            'signal_date': warnings.index[start],
            'last_above_threshold_date': warnings.index[end],
            'duration_observations': int(end - start + 1),
            'open_at_end': bool(end == len(warnings) - 1),
            'max_warning': float(warnings.iloc[start:end + 1].max()),
        })
    return pd.DataFrame.from_records(records, columns=EPISODE_COLUMNS)


def _event_ledger(classifications, peaks, severity):
    targets = peaks[peaks['severity'].eq('major')] if severity == 'major' else peaks[peaks['severity'].isin(['major', 'lower'])]
    useful = classifications[classifications['classification'].eq('detected')]
    records = []
    for peak in targets.itertuples(index=False):
        linked = useful[useful['associated_peak_date'].eq(peak.date)].sort_values('signal_date')
        records.append({
            'peak_date': peak.date,
            'severity': peak.severity,
            'detected': bool(len(linked)),
            'n_useful_episodes': len(linked),
            'first_signal_date': linked['signal_date'].iloc[0] if len(linked) else pd.NaT,
            'lead_trading_days': float(linked['lead_trading_days'].iloc[0]) if len(linked) else np.nan,
        })
    return pd.DataFrame.from_records(records, columns=EVENT_COLUMNS)


def _distribution(values):
    values = np.asarray(values, dtype=float)
    return {
        'count': len(values),
        'min': float(values.min()) if len(values) else None,
        'median': float(np.median(values)) if len(values) else None,
        'max': float(values.max()) if len(values) else None,
    }


def evaluate_catalog(warnings, peaks, calendar, config):
    """Evaluate one unchanged warning series against one explicit event catalog.

    Full-sample, warmup, censored and OOS metrics remain separate. OOS is a
    reporting slice after full-context classification, never a new episode
    start. Horizon sensitivity uses the same signals, labels and guard.
    The dictionaries contain JSON-safe metrics; ledgers are DataFrames.
    """
    calendar = _calendar(calendar)
    peaks = _peaks(peaks, calendar)
    series = _warning_series(warnings, calendar)
    threshold = float(config['threshold_warning'])
    first = collapse_signal_runs(series, threshold)
    episodes = _episodes(series, threshold)
    kwargs = {
        'trading_dates': calendar,
        'detection_window_days': config.get('detection_window_days', 240),
        'min_inter_peak_days': config.get('min_inter_peak_days', 80),
        'late_signal_days': config.get('late_signal_days', 10),
    }
    signals, censored_signals, events = {}, {}, {}
    full, after_warmup, endpoint_censored, out_of_sample = {}, {}, {}, {}
    lead_stats, event_lead_stats, horizon_rows = {}, {}, []
    for severity in ('major', 'lower'):
        cls = classify_first_signals(first, peaks, severity=severity, **kwargs)
        censored = classify_first_signals(first, peaks, severity=severity,
                                         censor_unresolved=True, **kwargs)
        signals[severity], censored_signals[severity] = cls, censored
        events[severity] = _event_ledger(cls, peaks, severity)
        full[severity] = compute_detection_metrics(cls, peaks, severity)
        after_warmup[severity] = compute_detection_metrics(
            cls, peaks if len(series) else peaks.iloc[:0], severity,
            evaluation_start=series.index[0] if len(series) else None)
        endpoint_censored[severity] = compute_detection_metrics(censored, peaks, severity)
        if config.get('insample_end'):
            out_of_sample[severity] = compute_detection_metrics(
                cls, peaks, severity,
                evaluation_start=pd.Timestamp(config['insample_end']) + pd.Timedelta(days=1))
        lead_stats[severity] = _distribution(cls.loc[cls['classification'].eq('detected'), 'lead_trading_days'])
        event_lead_stats[severity] = _distribution(events[severity].loc[events[severity]['detected'].eq(True), 'lead_trading_days'])
        for horizon in HORIZONS:
            horizon_cls = classify_first_signals(first, peaks, severity=severity,
                                                 **{**kwargs, 'detection_window_days': horizon})
            horizon_rows.append({'horizon_observations': horizon, 'severity': severity,
                                 **compute_detection_metrics(horizon_cls, peaks, severity)})
    above_count = int((series > threshold).sum())
    return {
        'metrics': {
            'full_sample': full,
            'after_warmup': after_warmup,
            'endpoint_censored': endpoint_censored,
            'out_of_sample': {
                'status': 'configured' if out_of_sample else 'not_configured',
                'insample_end': (pd.Timestamp(config['insample_end']).date().isoformat()
                                 if config.get('insample_end') else None),
                'metrics': out_of_sample,
                'note': 'fixed thresholds; no fitting; retrospective labels and historical peak context retained',
            },
        },
        'signals': signals,
        'censored_signals': censored_signals,
        'events': events,
        'episodes': episodes,
        'diagnostics': {
            'eligible_warning_days': len(series),
            'days_above_threshold': above_count,
            'days_above_threshold_pct': 100.0 * above_count / len(series) if len(series) else None,
            'alarm_fraction': above_count / len(series) if len(series) else None,
            'n_episodes': len(episodes),
            'open_episodes_at_end': int(episodes['open_at_end'].sum()) if len(episodes) else 0,
            'episode_duration_observations': _distribution(episodes['duration_observations']),
            'useful_episode_lead_observations': lead_stats,
            'detected_event_first_lead_observations': event_lead_stats,
            'calendar': 'supplied observed sessions; no fill or calendar approximation',
            'label_warning': 'catalog is retrospective; these metrics do not establish prospective or trading performance',
        },
        'horizons': pd.DataFrame.from_records(horizon_rows),
    }
