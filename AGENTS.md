# Repository: qca-retrospective-rogue-wave-identification-in-volatil

## Purpose
Reproduces a paper's rogue-wave-like volatility extreme identification methodology on VIX, VXO,
and VSTOXX daily high series using FFT envelope extraction, Schrödinger localization analysis,
and a real-time minimum-eigenvalue-gradient warning indicator.

## Key Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `data_loader` | `data/data_loader.py` | Loads daily high series (Yahoo Finance / Massive fallback) |
| `signal_processing` | `src/signal_processing.py` | mirror_series, spectral_peak_filter, reconstruct, extract_envelope |
| `peak_detection` | `src/peak_detection.py` | detect_peaks_and_prominences, compute_swh, classify_rogue_peaks |
| `schrodinger` | `src/schrodinger.py` | build_operator, solve_min_eigenpair, compute_width, compute_localization_distance |
| `diagnostics` | `src/diagnostics.py` | compute_lambda_series, compute_gradient_series |
| `realtime_pipeline` | `src/realtime_pipeline.py` | process_history_until, compute_warning_indicator |
| `evaluation` | `src/evaluation.py` | collapse_signal_runs, classify_first_signals, compute_detection_metrics |
| `plotting` | `src/plotting.py` | figure_1, figure_2, figure_3 style outputs |

## Critical Implementation Choices

- **Mirroring:** Symmetric reflection `x + x[-2:0:-1]` (excludes endpoint duplicate)
- **Spectral filter:** Detects spectral peaks via `scipy.signal.find_peaks` on amplitude spectrum,
  computes percentile threshold over detected-peak amplitudes, zeros sub-threshold components
- **Denoising percentile:** 92.5% for Exp1–3 (descriptive), 95% for Exp4–6 (real-time)
- **Boundary conditions:** Dirichlet (zeros at both window endpoints of the 80-day window)
- **H diagonal:** `1 + U_k`; off-diagonals: `−0.5`; δt = 1
- **Width:** `sqrt(trapz(|v|² * (k - k0)²) / trapz(|v|²))`, k0 = argmax(|v|)
- **Gradient:** `numpy.gradient` on `|λ_min|` sequence
- **Signal collapsing:** New episode when W_i crosses from ≤threshold to >threshold
- **Late signal:** Any signal within 10 trading days AFTER a peak (including same-day)
- **SWH:** Mean of top `ceil(n/3)` prominences

## Data Availability

- **VIX (`^VIX`):** Available via Yahoo Finance ✅
- **VXO (`^VXO`):** Delisted on Yahoo Finance — use synthetic or vendor data ⚠️
- **VSTOXX (`^V2TX`):** Not found on Yahoo Finance — use synthetic or vendor data ⚠️

## Test Suite

60 tests in `tests/`; all passing as of last run (0.46s).  
Run with: `pytest tests/ -q`

## Environment Variables

- `MASSIVE_TOKEN`: Massive API key (optional; falls back to Yahoo Finance if unset)

## Known Deviations from Paper

1. False-signal rate in Exp4 is ~42% vs paper's 0% — attributable to post-crisis recovery
   window re-firing and unresolved spectral-peak conjugate-frequency handling.
2. VXO/VSTOXX results use synthetic data due to ticker unavailability on Yahoo Finance.
3. Exact SWH values and peak dates may shift slightly based on sample endpoint.
