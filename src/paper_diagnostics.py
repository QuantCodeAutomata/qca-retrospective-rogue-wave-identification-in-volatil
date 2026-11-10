"""Descriptive Figure 5 / Supplement S1--S4 calculations.

The conventions not specified by the manuscript are frozen in
docs/SUPPLEMENT_PROTOCOL.md. These diagnostics never construct warnings,
select thresholds, or modify the input warning ledger.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from src.peak_detection import compute_swh, detect_peaks_and_prominences
from src.signal_processing import process_series


S1_WINDOWS = (("2008-10-13", 300), ("2020-03-16", 150), ("2011-08-09", 300))
S2_LAGS = (1, 2, 5, 10, 20)
INTERPRETATION = "descriptive_only; documented interpretation, not certified author reproduction"


def _validate_highs(highs):
    if not isinstance(highs, pd.Series) or not isinstance(highs.index, pd.DatetimeIndex):
        raise ValueError("highs must be a Series with a DatetimeIndex")
    if (highs.empty or highs.index.hasnans or highs.index.has_duplicates
            or not highs.index.is_monotonic_increasing):
        raise ValueError("highs must have a nonempty sorted unique observed calendar")
    values = highs.to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("highs must be finite and positive")


def _warning_copy(highs, warnings):
    required = {"date", "M_i", "C_i", "W_i", "event_date"}
    if not required.issubset(warnings.columns):
        raise ValueError(f"warning columns missing: {sorted(required - set(warnings.columns))}")
    result = warnings.copy(deep=True)
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    result["event_date"] = pd.to_datetime(result["event_date"], errors="raise")
    dates = pd.DatetimeIndex(result["date"])
    events = pd.DatetimeIndex(result["event_date"])
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("warning dates must be sorted, unique and nonmissing")
    if events.hasnans or (highs.index.get_indexer(dates) < 0).any():
        raise ValueError("warning dates must belong to the supplied calendar")
    if (highs.index.get_indexer(events) < 0).any() or (events > dates).any():
        raise ValueError("event_date must be an observed date no later than signal date")
    if not np.isfinite(result[["M_i", "C_i", "W_i"]].to_numpy(dtype=float)).all():
        raise ValueError("warning values must be finite")
    return result


def lagged_gradient_correlation(highs, warnings, lags=range(-30, 31), min_gradient=1e-4):
    """Pearson corr(M_i, High[i+lag]); positive lag means future High.

    Shift on the full observed input calendar, before filtering M_i. Filtering
    first would turn a lag into a count of selected warning days.
    """
    _validate_highs(highs)
    if not np.isfinite(min_gradient):
        raise ValueError("min_gradient must be finite")
    warnings = _warning_copy(highs, warnings)
    positions = highs.index.get_indexer(pd.DatetimeIndex(warnings["date"]))
    gradients = warnings["M_i"].to_numpy(dtype=float)
    values = highs.to_numpy(dtype=float)
    records = []
    for lag in lags:
        if isinstance(lag, (bool, np.bool_)) or int(lag) != lag:
            raise ValueError("lags must be integers")
        target = positions + int(lag)
        keep = (target >= 0) & (target < len(values)) & (gradients > min_gradient)
        x, y = gradients[keep], values[target[keep]]
        r, status = None, "completed"
        if len(x) < 2:
            status = "insufficient_pairs"
        elif np.ptp(x) == 0 or np.ptp(y) == 0:
            status = "constant_input"
        else:
            r = float(np.corrcoef(x, y)[0, 1])
            if not np.isfinite(r):
                raise FloatingPointError("Pearson correlation returned a nonfinite result")
        records.append({"lag_observations": int(lag), "pearson_r": r,
                        "n_pairs": int(len(x)), "status": status})
    return pd.DataFrame(records)


def omori_integral(t, c, p):
    """Integral of (s+c)**(-p) from 0 to t, stable at p=1."""
    t = np.asarray(t, dtype=float)
    if not np.isfinite(t).all() or np.any(t < 0) or not np.isfinite(c) or c <= 0:
        raise ValueError("Omori requires finite t>=0 and c>0")
    if not np.isfinite(p) or p < 0:
        raise ValueError("Omori p must be finite and nonnegative")
    log_ratio = np.log1p(t / c)
    if abs(p - 1.0) < 1e-8:
        return log_ratio
    q = 1.0 - p
    return c**q * np.expm1(q * log_ratio) / q


def fit_omori_counts(cumulative_counts):
    """Prespecified nine-start, bounded, unweighted cumulative-count fit."""
    counts = np.asarray(cumulative_counts, dtype=float)
    if (counts.ndim != 1 or len(counts) < 2 or not np.isfinite(counts).all()
            or counts[0] != 0 or np.any(np.diff(counts) < 0)
            or np.any(counts != np.floor(counts))):
        raise ValueError("counts must be nondecreasing integer counts beginning at N(0)=0")
    horizon, n_events = len(counts) - 1, int(counts[-1])
    result = {"status": "no_events" if not n_events else "insufficient_events",
              "n_events": n_events, "horizon_observations": horizon,
              "K": None, "c": None, "p": None, "sse": None, "r_squared": None,
              "starts_attempted": 0, "starts_converged": 0}
    if n_events < 3:
        return result
    if horizon < 3:
        raise ValueError("at least three post-anchor observations are needed")
    t, y = np.arange(1, horizon + 1, dtype=float), counts[1:]

    def profile(theta):
        p, c = float(theta[0]), float(np.exp(theta[1]))
        f = omori_integral(t, c, p)
        k = max(0.0, float(np.dot(f, y) / np.dot(f, f)))
        return k * f - y, k, c, p

    candidates = []
    failures = []
    for p0 in (0.25, 1.0, 2.0):
        for c0 in (1.0, 10.0, horizon / 3.0):
            # The public entrypoint uses H=150 or300; clipping keeps this helper
            # well-defined for shorter test/research windows without extra starts.
            c0 = min(max(c0, 0.1), horizon)
            result["starts_attempted"] += 1
            try:
                fit = least_squares(lambda theta: profile(theta)[0],
                                    [p0, np.log(c0)],
                                    bounds=([0.0, np.log(0.1)], [3.0, np.log(horizon)]),
                                    ftol=1e-10, xtol=1e-10, gtol=1e-10, max_nfev=10000)
                residual, k, c, p = profile(fit.x)
                if fit.success and np.isfinite(residual).all():
                    candidates.append((float(np.dot(residual, residual)), p, c, k))
                else:
                    failures.append(str(fit.message))
            except (ValueError, FloatingPointError, OverflowError, RuntimeError) as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
    result["starts_converged"] = len(candidates)
    result["failed_start_messages"] = failures
    if not candidates:
        result["status"] = "optimizer_failed"
        return result
    minimum_sse = min(item[0] for item in candidates)
    tied = [item for item in candidates
            if abs(item[0] - minimum_sse) <= 1e-10 * max(1.0, minimum_sse)]
    sse, p, c, k = min(tied, key=lambda item: (item[1], item[2]))
    boundary = (np.isclose(p, 0.0, atol=1e-6, rtol=0)
                or np.isclose(p, 3.0, atol=1e-6, rtol=0)
                or np.isclose(c, 0.1, atol=1e-6, rtol=0)
                or np.isclose(c, horizon, atol=1e-6, rtol=1e-6)
                or np.isclose(k, 0.0, atol=1e-10, rtol=0))
    sst = float(np.sum((y - y.mean()) ** 2))
    result.update(status="boundary_solution" if boundary else "completed",
                  K=k, c=c, p=p, sse=sse,
                  r_squared=(1 - sse / sst) if sst > 0 else None)
    return result


def aftershock_window(highs, raw_peaks, anchor, horizon):
    """Count selected raw peak prominences; anchor itself is never counted."""
    anchor = pd.Timestamp(anchor)
    if anchor not in highs.index:
        return None, {"status": "unavailable", "reason": "anchor_absent"}
    start = int(highs.index.get_loc(anchor))
    if start + horizon >= len(highs):
        return None, {"status": "unavailable", "reason": "insufficient_post_anchor_history"}
    indices = np.arange(start, start + horizon + 1)
    selected_dates = pd.DatetimeIndex(raw_peaks.loc[raw_peaks["exceeds_swh"], "date"])
    is_event = highs.index[indices].isin(selected_dates)
    is_event[0] = False
    frame = pd.DataFrame({"date": highs.index[indices], "global_index_1based": indices + 1,
                          "observations_since_anchor": np.arange(horizon + 1),
                          "high": highs.iloc[indices].to_numpy(), "aftershock": is_event,
                          "cumulative_count": np.cumsum(is_event, dtype=int)})
    return frame, {"status": "completed", "anchor": str(anchor.date()),
                   "horizon_observations": horizon, "n_events": int(is_event.sum())}


def log_index_decay(envelope, window):
    """OLS log(envelope) on log(global 1-based frozen-sample index)."""
    positions = window["global_index_1based"].to_numpy(dtype=int)
    values = np.asarray(envelope, dtype=float)[positions - 1]
    if not np.isfinite(values).all() or np.any(values <= 0):
        return None, {"status": "failed", "reason": "nonpositive_or_nonfinite_envelope"}
    x, y = np.log(positions), np.log(values)
    if len(x) < 2 or np.ptp(x) == 0:
        return None, {"status": "unavailable", "reason": "insufficient_index_range"}
    # Center the predictor to avoid poor conditioning from a narrow interval
    # of large global indices, then recover the requested global intercept.
    xc, yc = x - x.mean(), y - y.mean()
    slope = float(np.dot(xc, yc) / np.dot(xc, xc))
    intercept = float(y.mean() - slope * x.mean())
    fitted = intercept + slope * x
    sse, sst = float(np.sum((y - fitted) ** 2)), float(np.dot(yc, yc))
    frame = window[["date", "global_index_1based"]].copy()
    frame["envelope"], frame["log_index"], frame["log_envelope"] = values, x, y
    frame["fitted_log_envelope"] = fitted
    return frame, {"status": "completed", "slope": slope, "intercept": intercept,
                   "n_observations": len(x), "sse": sse,
                   "r_squared": (1 - sse / sst) if sst > 0 else None}


def envelope_increment_diagnostics(dates, envelope, lags=S2_LAGS, bins=100):
    """Raw and standardized differences, shared 100-bin edges per panel."""
    values = np.asarray(envelope, dtype=float)
    dates = pd.DatetimeIndex(dates)
    if values.ndim != 1 or len(values) != len(dates) or not np.isfinite(values).all():
        raise ValueError("envelope must be finite and aligned with dates")
    rows, summaries = [], []
    for lag in lags:
        if isinstance(lag, (bool, np.bool_)) or int(lag) != lag or lag <= 0:
            raise ValueError("increment lags must be positive integers")
        lag = int(lag)
        delta = values[lag:] - values[:-lag]
        if not len(delta):
            summaries.append({"lag_observations": lag, "n": 0, "mean": None,
                              "std_ddof0": None, "status": "insufficient_history"})
            continue
        mean, std = float(delta.mean()), float(delta.std(ddof=0))
        standardized = (delta - mean) / std if std > 0 else np.full(len(delta), np.nan)
        rows.append(pd.DataFrame({"lag_observations": lag, "start_date": dates[:-lag],
                                  "end_date": dates[lag:], "increment": delta,
                                  "standardized_increment": standardized}))
        summaries.append({"lag_observations": lag, "n": len(delta), "mean": mean,
                          "std_ddof0": std,
                          "status": "completed" if std > 0 else "zero_variance"})
    columns = ["lag_observations", "start_date", "end_date", "increment", "standardized_increment"]
    increments = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=columns)
    histograms, edge_metadata = [], {}
    for representation, column in (("raw", "increment"), ("standardized", "standardized_increment")):
        pooled = increments[column].to_numpy(dtype=float)
        pooled = pooled[np.isfinite(pooled)]
        if not len(pooled):
            edge_metadata[representation] = []
            continue
        edges = np.histogram_bin_edges(pooled, bins=bins)
        edge_metadata[representation] = edges.tolist()
        for lag, group in increments.groupby("lag_observations", sort=True):
            data = group[column].to_numpy(dtype=float)
            data = data[np.isfinite(data)]
            if not len(data):
                continue
            counts, _ = np.histogram(data, bins=edges)
            histograms.append(pd.DataFrame({"representation": representation,
                                            "lag_observations": int(lag), "bin_left": edges[:-1],
                                            "bin_right": edges[1:], "count": counts,
                                            "probability_density": counts / (len(data) * np.diff(edges)),
                                            "n_observations": len(data)}))
    hist_columns = ["representation", "lag_observations", "bin_left", "bin_right",
                    "count", "probability_density", "n_observations"]
    hist = pd.concat(histograms, ignore_index=True) if histograms else pd.DataFrame(columns=hist_columns)
    return increments, hist, {"lags": summaries, "bin_count": bins,
                              "shared_bin_edges": edge_metadata, "standardization_ddof": 0}


def _json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def run_paper_diagnostics(index_name, highs, warnings, config, output_dir,
                          descriptive_envelope=None):
    """Write inspectable descriptive figures/tables; return per-figure statuses.

    ``None`` or empty warnings make Fig5/S3/S4 unavailable where applicable.
    Invalid supplied data still raise; absence is not a numerical failure.
    """
    from src import paper_plots

    _validate_highs(highs)
    index_name = str(index_name).upper()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = f"paper_{index_name.lower()}"
    summary = {"index": index_name, "interpretation": INTERPRETATION,
               "protocol": "docs/SUPPLEMENT_PROTOCOL.md", "filter_mode": config.get("filter_mode", "spectral_peaks"),
               "descriptive_percentile": float(config.get("filter_percentile_descriptive", 92.5)),
               "is_synthetic": bool(highs.attrs.get("is_synthetic", False)),
               "input_start": str(highs.index[0].date()), "input_end": str(highs.index[-1].date()),
               "figures": {}}
    ledger = None if warnings is None or warnings.empty else _warning_copy(highs, warnings)

    def csv(frame, suffix):
        name = f"{prefix}_{suffix}.csv"
        frame.to_csv(output / name, index=False)
        return name

    if ledger is None:
        summary["figures"]["figure5"] = {"status": "unavailable", "reason": "warnings_not_supplied"}
    else:
        correlation = lagged_gradient_correlation(highs, ledger)
        table = csv(correlation, "figure5_correlation")
        figure = f"{prefix}_figure5_correlation.png"
        paper_plots.correlation(correlation, index_name, output / figure, summary["is_synthetic"])
        summary["figures"]["figure5"] = {"status": "completed", "table": table, "figure": figure,
                                          "positive_lag": "future High relative to signal_date",
                                          "min_gradient_exclusive": 1e-4,
                                          "n_defined_lags": int(correlation["pearson_r"].notna().sum())}

    if index_name == "VIX":
        if descriptive_envelope is not None and np.iscomplexobj(descriptive_envelope):
            raise ValueError("descriptive_envelope must be real-valued")
        envelope = (process_series(highs.to_numpy(dtype=float), summary["descriptive_percentile"],
                                   filter_mode=summary["filter_mode"])
                    if descriptive_envelope is None else np.asarray(descriptive_envelope, dtype=float))
        if (envelope.ndim != 1 or len(envelope) != len(highs)
                or not np.isfinite(envelope).all() or np.any(envelope < 0)):
            raise ValueError("descriptive_envelope must be nonnegative, finite and aligned with highs")
        peaks, prominences = detect_peaks_and_prominences(highs.to_numpy(dtype=float))
        swh = compute_swh(prominences)
        raw = pd.DataFrame({"date": highs.index[peaks], "global_index_1based": peaks + 1,
                            "high": highs.iloc[peaks].to_numpy(), "prominence": prominences,
                            "exceeds_swh": prominences > swh})
        s1 = {"status": "completed", "raw_swh": swh,
              "raw_peak_table": csv(raw, "s1_raw_peaks"), "windows": {},
              "definition": "raw local peak prominence strictly exceeds full-sample raw SWH"}
        windows = {}
        for anchor, horizon in S1_WINDOWS:
            frame, detail = aftershock_window(highs, raw, anchor, horizon)
            if frame is not None:
                fit = fit_omori_counts(frame["cumulative_count"].to_numpy())
                detail["fit"] = fit
                frame["fitted_count"] = (fit["K"] * omori_integral(
                    frame["observations_since_anchor"].to_numpy(), fit["c"], fit["p"])
                    if fit["K"] is not None else np.nan)
                detail["table"] = csv(frame, f"s1_aftershocks_{anchor}")
                windows[anchor] = frame
            s1["windows"][anchor] = detail
        log_frame = None
        if "2008-10-13" in windows:
            log_frame, s1["log_index_fit"] = log_index_decay(envelope, windows["2008-10-13"])
            if log_frame is not None:
                s1["log_index_fit"]["table"] = csv(log_frame, "s1_log_index_decay")
        else:
            s1["log_index_fit"] = {"status": "unavailable", "reason": "2008_window_unavailable"}
        if not windows:
            s1["status"] = "unavailable"
        elif len(windows) != len(S1_WINDOWS) or s1["log_index_fit"]["status"] != "completed":
            s1["status"] = "partial"
        elif any(d["fit"]["status"] not in {"completed", "boundary_solution"}
                 for d in s1["windows"].values()):
            s1["status"] = "partial"
        s1["figure"] = f"{prefix}_s1_aftershocks.png"
        paper_plots.aftershocks(windows, log_frame, s1, output / s1["figure"], summary["is_synthetic"])
        summary["figures"]["S1"] = s1

        increments, histograms, increment_meta = envelope_increment_diagnostics(highs.index, envelope)
        s2 = {"status": ("completed" if all(x["status"] == "completed" for x in increment_meta["lags"])
                          else "partial"), "increments_table": csv(increments, "s2_increments"),
              "histogram_table": csv(histograms, "s2_histograms"), **increment_meta,
              "figure": f"{prefix}_s2_increments.png"}
        paper_plots.increments(histograms, output / s2["figure"], summary["is_synthetic"])
        summary["figures"]["S2"] = s2
    else:
        summary["figures"]["S1"] = {"status": "not_applicable", "reason": "VIX_only_in_manuscript"}
        summary["figures"]["S2"] = {"status": "not_applicable", "reason": "VIX_only_in_manuscript"}

    for label, applicable, years in (("S3", "VIX", (2018, 2020)), ("S4", "VXO", (2020,))):
        if index_name != applicable:
            summary["figures"][label] = {"status": "not_applicable", "reason": f"{applicable}_only_in_manuscript"}
            continue
        if ledger is None:
            summary["figures"][label] = {"status": "unavailable", "reason": "warnings_not_supplied"}
            continue
        selected = {}
        details = {}
        for year in years:
            frame = ledger.loc[ledger["date"].dt.year == year].copy()
            if frame.empty:
                details[str(year)] = {"status": "unavailable", "reason": "no_warning_rows_in_year"}
            else:
                selected[year] = frame
                details[str(year)] = {"status": "completed", "n_rows": len(frame),
                                      "n_unique_event_dates": int(frame["event_date"].nunique()),
                                      "first_signal_date": str(frame["date"].iloc[0].date()),
                                      "last_signal_date": str(frame["date"].iloc[-1].date()),
                                      "table": csv(frame, f"{label.lower()}_{year}_received_and_event")}
        status = "completed" if len(selected) == len(years) else "partial" if selected else "unavailable"
        info = {"status": status, "years": details, "repeated_event_dates": "preserved; no deduplication"}
        if selected:
            info["figure"] = f"{prefix}_{label.lower()}_received_and_event.png"
            paper_plots.received_and_event(highs, selected, label,
                                           float(config.get("threshold_warning", 700 if index_name == "VXO" else 300)),
                                           output / info["figure"], summary["is_synthetic"])
        summary["figures"][label] = info

    name = f"{prefix}_diagnostics_summary.json"
    summary["summary_path"] = name
    _json(output / name, summary)
    return summary
