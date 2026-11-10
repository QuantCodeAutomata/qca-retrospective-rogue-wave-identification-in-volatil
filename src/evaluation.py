"""Event-level evaluation using the actual observed trading calendar.

The paper's Table 1--3 precision excludes false, low AND late signals.
Its false-signal category is shared between severity levels: warnings of a
2--2.5 SWH event are low signals, not false alarms. These ex-post scores do
not constitute a trading backtest or prospective validation.
"""
import numpy as np
import pandas as pd


CLASSIFICATION_COLUMNS = ['signal_date', 'classification', 'associated_peak_date',
                          'lead_trading_days', 'days_since_previous_peak']


def _calendar(dates: pd.DatetimeIndex, name: str) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(dates)
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError(f'{name} must be sorted, unique and contain no NaT')
    return dates


def _target_peaks(peak_df: pd.DataFrame, severity: str) -> pd.DataFrame:
    if severity not in ('major', 'lower'):
        raise ValueError("severity must be 'major' or 'lower' (major+lower)")
    if not {'date', 'severity'}.issubset(peak_df.columns):
        raise ValueError('peak_df must have date and severity columns')
    selected = ['major'] if severity == 'major' else ['major', 'lower']
    return peak_df[peak_df['severity'].isin(selected)].copy()


def collapse_signal_runs(signal_series: pd.Series, threshold: float) -> pd.DatetimeIndex:
    """Collapse contiguous above-threshold observations into first dates.

    Missing/non-finite observations raise: otherwise a missing calculation
    would silently end one episode and create another first signal.
    """
    dates = _calendar(signal_series.index, 'signal_series index')
    values = signal_series.to_numpy(dtype=float)
    if not np.isfinite(values).all() or not np.isfinite(threshold):
        raise ValueError('Signals and threshold must be finite')
    above = values > threshold
    starts = above & ~np.r_[False, above[:-1]] if len(above) else above
    return dates[starts]


def classify_first_signals(first_signal_dates: pd.DatetimeIndex, peak_df: pd.DataFrame,
                           severity: str = 'major', detection_window_days: int = 240,
                           min_inter_peak_days: int = 80, late_signal_days: int = 10,
                           *, trading_dates: pd.DatetimeIndex,
                           censor_unresolved: bool = False,
                           observation_end=None) -> pd.DataFrame:
    """Classify warnings by exact trading-observation offsets.

    All historical peaks and the FULL observed trading calendar must be passed
    even when subsequently evaluating only an OOS period. Select that period
    in ``compute_detection_metrics``, after classification.

    Rules follow p9 and Supplementary Tables 1--3. A major event within the
    horizon is preferred even when a lower event occurs first (S2, 1997).
    Same-day signals count as late (S1, 2018). After a lower event a warning is
    ``low`` for major scoring and ``late`` for major+lower scoring (S1, 2024).
    The under-specified 11..80-day post-peak interval is explicitly ``recovery``
    when it otherwise points to the next target; it never earns detection.

    By default a warning with no qualifying event left in the frozen sample
    is false, matching the paper's finite-sample convention. With
    ``censor_unresolved=True``, such warnings are censored unless a full
    detection horizon has elapsed. This option is recommended for a live or
    independently held-out endpoint; censored warnings remain in the ledger
    but are excluded from precision denominators.

    ``observation_end`` is an as-of cutoff, not merely a reporting filter.
    Future signals, peaks and calendar observations are removed before any
    classification, and unresolved horizons are censored automatically. A
    cutoff between sessions uses the last supplied session before it. This
    does not make full-sample peak labels causal: supply independently frozen
    labels when that property is required.
    """
    calendar = _calendar(trading_dates, 'trading_dates')
    signals = _calendar(first_signal_dates, 'first_signal_dates')
    targets = _target_peaks(peak_df, severity)
    all_peaks = _target_peaks(peak_df, 'lower')
    all_peaks['date'] = pd.to_datetime(all_peaks['date'])
    all_peaks = all_peaks.sort_values('date')
    for name, value in [('detection_window_days', detection_window_days),
                        ('min_inter_peak_days', min_inter_peak_days),
                        ('late_signal_days', late_signal_days)]:
        if not np.isfinite(value) or int(value) != value or value < 0:
            raise ValueError(f'{name} must be a nonnegative integer')
    if detection_window_days == 0:
        raise ValueError('detection_window_days must be positive')
    signal_pos = calendar.get_indexer(signals)
    all_dates = pd.DatetimeIndex(all_peaks['date'])
    target_dates = pd.DatetimeIndex(targets['date']).sort_values()
    if all_dates.hasnans or all_dates.has_duplicates:
        raise ValueError('Extreme peak dates must be nonmissing and unique')
    all_pos = calendar.get_indexer(all_dates)
    target_pos = calendar.get_indexer(target_dates)
    if (signal_pos < 0).any() or (all_pos < 0).any():
        raise ValueError('Every signal and extreme peak must lie on trading_dates')
    if observation_end is not None:
        cutoff = pd.Timestamp(observation_end)
        if pd.isna(cutoff):
            raise ValueError('observation_end must be a valid date')
        calendar = calendar[calendar <= cutoff]
        keep_signals = signal_pos < len(calendar)
        signals, signal_pos = signals[keep_signals], signal_pos[keep_signals]
        all_pos = all_pos[all_pos < len(calendar)]
        target_pos = target_pos[target_pos < len(calendar)]
        censor_unresolved = True
    records = []
    for sig_date, s in zip(signals, signal_pos):
        prev_any = all_pos[all_pos <= s]
        prev_target = target_pos[target_pos <= s]
        next_any = all_pos[all_pos > s]
        next_target = target_pos[target_pos > s]
        last_any = int(prev_any[-1]) if len(prev_any) else None
        last_target = int(prev_target[-1]) if len(prev_target) else None
        future_any = int(next_any[0]) if len(next_any) else None
        future_target = int(next_target[0]) if len(next_target) else None
        since_target = s - last_target if last_target is not None else np.nan
        within_any = future_any is not None and future_any - s <= detection_window_days
        within_target = (future_target is not None and
                         future_target - s <= detection_window_days)
        assoc = None
        if last_target is not None and s - last_target <= late_signal_days:
            category, assoc = 'late', last_target
        elif last_any is not None and s - last_any <= late_signal_days:
            # Only possible for major scoring after a lower event.
            category, assoc = 'low', last_any
        elif within_target:
            assoc = future_target
            if last_target is not None and since_target <= min_inter_peak_days:
                category = 'recovery'
            else:
                category = 'detected'
        elif (censor_unresolved and
              len(calendar) - 1 - s < detection_window_days):
            # A known lower event does not settle major scoring while an
            # unobserved major could still arrive within the same horizon.
            category, assoc = 'censored', future_any if within_any else None
        elif within_any:
            category, assoc = 'low', future_any
        else:
            category = 'false'
        records.append({
            'signal_date': sig_date,
            'classification': category,
            'associated_peak_date': calendar[assoc] if assoc is not None else pd.NaT,
            'lead_trading_days': float(assoc - s) if assoc is not None else np.nan,
            'days_since_previous_peak': float(since_target),
        })
    result = pd.DataFrame.from_records(records, columns=CLASSIFICATION_COLUMNS)
    # An explicit end-date aggregate must know that *all* categories were
    # resolved at that cutoff, including false warnings with no association.
    # DataFrame copies retain attrs; a CSV reload requires reclassification.
    result.attrs['observation_end'] = (
        pd.Timestamp(observation_end).normalize().isoformat()
        if observation_end is not None else None)
    return result


def compute_detection_metrics(classification_df: pd.DataFrame, peak_df: pd.DataFrame,
                              severity: str = 'major', *, evaluation_start=None,
                              evaluation_end=None) -> dict:
    """Compute distinct event recall and signal precision over an explicit scope.

    Both warning dates and target peak dates must fall inside the requested
    inclusive scope. A signal before an OOS boundary cannot earn OOS recall;
    a signal continuing across the boundary is not artificially re-fired.
    Classification must first use all historical context, not sliced peaks.
    This function only aggregates an existing ledger. For an as-of
    ``evaluation_end``, first classify with ``observation_end`` set to that
    cutoff; merely slicing a full-history ledger cannot resolve immature
    false/low warnings correctly. The classifier's ``observation_end`` attr
    must match the end date. CSV reloads lose this metadata and must be
    reclassified before end-date scoring. No categories are changed here.

    ``n_detected`` counts useful SIGNALS, while ``n_unique_detected_peaks``
    counts distinct detected EVENTS. They are different denominators.
    No events/signals yields an undefined percentage (None), not a fake 0%.
    """
    if evaluation_end is not None:
        end = pd.Timestamp(evaluation_end)
        classified_end = classification_df.attrs.get('observation_end')
        if (pd.isna(end) or classified_end is None or
                pd.Timestamp(classified_end).normalize() != end.normalize()):
            raise ValueError('Classify with matching observation_end before aggregating evaluation_end; '
                             'CSV-reloaded ledgers require reclassification')
    targets = _target_peaks(peak_df, severity)
    targets['date'] = pd.to_datetime(targets['date'])
    if targets['date'].isna().any() or targets['date'].duplicated().any():
        raise ValueError('Target peak dates must be nonmissing and unique')
    cls = classification_df.copy()
    required = {'signal_date', 'classification', 'associated_peak_date'}
    if not required.issubset(cls.columns):
        if cls.empty:
            cls = pd.DataFrame(columns=sorted(required))
        else:
            raise ValueError('classification_df is missing required columns')
    cls['signal_date'] = pd.to_datetime(cls['signal_date'])
    cls['associated_peak_date'] = pd.to_datetime(cls['associated_peak_date'])
    if cls['signal_date'].isna().any() or cls['signal_date'].duplicated().any():
        raise ValueError('Signal dates must be nonmissing and unique')
    if evaluation_start is not None and evaluation_end is not None:
        if pd.Timestamp(evaluation_start) > pd.Timestamp(evaluation_end):
            raise ValueError('evaluation_start must not exceed evaluation_end')
    for bound, op in [(evaluation_start, 'start'), (evaluation_end, 'end')]:
        if bound is None:
            continue
        bound = pd.Timestamp(bound)
        if op == 'start':
            targets = targets[targets['date'] >= bound]
            cls = cls[cls['signal_date'] >= bound]
        else:
            targets = targets[targets['date'] <= bound]
            cls = cls[cls['signal_date'] <= bound]
    allowed = {'detected', 'false', 'late', 'low', 'recovery', 'censored'}
    if not cls['classification'].isin(allowed).all():
        raise ValueError('Unknown signal classification')
    # A future association proves this is not a ledger classified at the cutoff.
    if evaluation_end is not None:
        future = cls['associated_peak_date'] > pd.Timestamp(evaluation_end)
        if future.any():
            raise ValueError('Classify with observation_end before aggregating evaluation_end')
    counts = cls['classification'].value_counts()
    n_signals = len(cls)
    n_censored = int(counts.get('censored', 0))
    n_evaluated = n_signals - n_censored
    n_detected = int(counts.get('detected', 0))
    n_false = int(counts.get('false', 0))
    n_late = int(counts.get('late', 0))
    n_peaks = len(targets)
    useful = cls.loc[cls['classification'] == 'detected', 'associated_peak_date'].dropna()
    all_target_dates = pd.DatetimeIndex(_target_peaks(peak_df, severity)['date'])
    if not useful.isin(all_target_dates).all():
        raise ValueError('Detected signals must reference a target-severity peak')
    detected_peaks = useful[useful.isin(targets['date'])].nunique()
    def pct(numerator, denominator):
        return 100.0 * numerator / denominator if denominator else None
    return {
        'peaks_detected_pct': pct(detected_peaks, n_peaks),
        'false_signal_pct': pct(n_false, n_evaluated),
        'precision_pct': pct(n_detected, n_evaluated),
        'precision_excl_late_pct': pct(n_detected, n_evaluated - n_late),
        'n_peaks': n_peaks,
        'n_signals': n_signals,
        'n_evaluated_signals': n_evaluated,
        'n_detected': n_detected,
        'n_unique_detected_peaks': int(detected_peaks),
        'n_false': n_false,
        'n_late': n_late,
        'n_low': int(counts.get('low', 0)),
        'n_recovery': int(counts.get('recovery', 0)),
        'n_censored': n_censored,
    }
