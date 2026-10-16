import numpy as np
import pandas as pd


def collapse_signal_runs(
    signal_series: pd.Series,
    threshold: float
) -> pd.DatetimeIndex:
    """Collapse above-threshold runs into first-signal dates (threshold crossings)."""
    above = signal_series > threshold
    first_signals = []
    in_episode = False
    for date, val in above.items():
        if val and not in_episode:
            first_signals.append(date)
            in_episode = True
        elif not val:
            in_episode = False
    return pd.DatetimeIndex(first_signals)


def classify_first_signals(
    first_signal_dates: pd.DatetimeIndex,
    peak_df: pd.DataFrame,
    severity: str = 'major',
    detection_window_days: int = 240,
    min_inter_peak_days: int = 80,
    late_signal_days: int = 10
) -> pd.DataFrame:
    """Classify each first-signal date.

    Rules (paper §4):
    - 'detected': signal appears in the 240-trading-day window before a qualifying peak and
                  more than 80 trading days after the previous qualifying peak.
    - 'late'    : signal appears within late_signal_days trading days AFTER a qualifying peak.
    - 'false'   : signal is more than 240 trading days before any next peak (or none exists).

    Calendar-day approximations used throughout (240 td ≈ 347 cal days; 80 td ≈ 116 cal days;
    10 td ≈ 15 cal days) because trade-day counting is not available at this call site.

    severity='major' -> peaks where severity=='major'
    severity='lower' -> peaks where severity in ('major','lower')
    """
    if severity == 'major':
        target_peaks = peak_df[peak_df['severity'] == 'major']['date'].sort_values()
    else:
        target_peaks = peak_df[peak_df['severity'].isin(['major', 'lower'])]['date'].sort_values()
    target_peaks = pd.DatetimeIndex(target_peaks)

    # Calendar-day thresholds (approximations of trading-day limits)
    detect_cal = int(detection_window_days * 1.4)   # ~240 td → ~336 cal days
    late_cal = int(late_signal_days * 2.0)           # ~10 td  → ~20 cal days
    inter_cal = int(min_inter_peak_days * 1.4)       # ~80 td  → ~112 cal days

    records = []
    for sig_date in first_signal_dates:
        # 1. Check for a late signal: within late_cal days AFTER any qualifying peak.
        #    delta == 0 (same day as peak) also counts as late — the signal arrived
        #    too late to serve as a pre-event warning.
        is_late = False
        late_peak = None
        for pk in target_peaks:
            delta = (sig_date - pk).days
            if 0 <= delta <= late_cal:   # 0 included: same-day = late
                is_late = True
                late_peak = pk
                break

        # 2. Find the next qualifying peak within the detection window.
        assoc_peak = None
        for pk in target_peaks:
            delta_fwd = (pk - sig_date).days
            if 0 < delta_fwd <= detect_cal:
                # Also check minimum inter-peak gap (signal must be far enough from prev peak).
                prev_peaks = target_peaks[target_peaks < sig_date]
                if len(prev_peaks) > 0:
                    days_since_prev = (sig_date - prev_peaks[-1]).days
                    if days_since_prev <= inter_cal:
                        # Too close to previous peak — likely a late/spurious signal for it.
                        continue
                assoc_peak = pk
                break

        # 3. Classify.
        if is_late:
            # Late signals can have either a past peak (late_peak) or a future peak (assoc_peak).
            classification = 'late'
            associated = late_peak if assoc_peak is None else assoc_peak
        elif assoc_peak is not None:
            classification = 'detected'
            associated = assoc_peak
        else:
            classification = 'false'
            associated = None

        records.append({
            'signal_date': sig_date,
            'classification': classification,
            'associated_peak_date': associated,
        })
    return pd.DataFrame(records)


def compute_detection_metrics(
    classification_df: pd.DataFrame,
    peak_df: pd.DataFrame,
    severity: str = 'major'
) -> dict:
    """Compute performance metrics."""
    if severity == 'major':
        target_peaks = peak_df[peak_df['severity'] == 'major']
    else:
        target_peaks = peak_df[peak_df['severity'].isin(['major', 'lower'])]

    n_peaks = len(target_peaks)
    if classification_df.empty or n_peaks == 0:
        return {
            'peaks_detected_pct': 0.0,
            'false_signal_pct': 0.0,
            'precision_pct': 0.0,
            'precision_excl_late_pct': 0.0,
            'n_peaks': n_peaks,
            'n_signals': 0,
            'n_detected': 0,
            'n_false': 0,
            'n_late': 0,
        }

    n_signals = len(classification_df)
    n_detected = len(classification_df[classification_df['classification'] == 'detected'])
    n_false = len(classification_df[classification_df['classification'] == 'false'])
    n_late = len(classification_df[classification_df['classification'] == 'late'])

    # peaks_detected: unique peaks associated with detected (non-late) signals
    detected_peaks = classification_df[classification_df['classification'] == 'detected']['associated_peak_date'].dropna().unique()
    peaks_detected_pct = 100.0 * len(detected_peaks) / n_peaks if n_peaks > 0 else 0.0
    false_signal_pct = 100.0 * n_false / n_signals if n_signals > 0 else 0.0
    precision_pct = 100.0 * (n_detected + n_late) / n_signals if n_signals > 0 else 0.0
    precision_excl_late_pct = 100.0 * n_detected / (n_signals - n_late) if (n_signals - n_late) > 0 else 0.0

    return {
        'peaks_detected_pct': peaks_detected_pct,
        'false_signal_pct': false_signal_pct,
        'precision_pct': precision_pct,
        'precision_excl_late_pct': precision_excl_late_pct,
        'n_peaks': n_peaks,
        'n_signals': n_signals,
        'n_detected': n_detected,
        'n_false': n_false,
        'n_late': n_late,
    }
