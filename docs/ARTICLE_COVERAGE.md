# Article coverage

Source: Hayward, Lennon and Biancalana, arXiv:2606.31475v4, 15 October 2026. PDF SHA-256: `7e2ed7488fc993153404622d83c8e6ccd76eb41e701b76b5b34116b7349cf412`.

“Implemented” means a calculation exists and was checked. It does not mean that its values equal the authors' results. The [replication report](REPLICATION.md) gives the measured outcomes; the [supplement protocol](SUPPLEMENT_PROTOCOL.md) fixes the choices needed where the paper is incomplete.

| Paper item | Implementation | Check / result | Remaining assumption |
|---|---|---|---|
| Equation 1, NLS analogy | Motivation for the stationary operator | The described algorithm does not require evolving the NLS equation | No claim to simulate nonlinear market dynamics |
| Signal processing | `src/signal_processing.py` | FFT/Hilbert reference tests, mirror and conjugate symmetry, Hilbert before cropping | Mirror, spectral percentile and DC/Nyquist choices are not fully specified by the authors |
| SWH and rogue peaks | `src/peak_detection.py` | Strict >2 and >2.5 thresholds; separate raw and envelope SWH | Largest third uses ceil; full-history labels are retrospective |
| Equations 2–4, operator/eigenpair | `src/schrodinger.py` | Constant-potential analytic spectrum, boundary, orthonormality and Rayleigh checks | Raw amplitude, dt = 1; endpoint and ghost Dirichlet choices are explicit |
| Equation 5, width/localization | `src/schrodinger.py`, Exp2 | Trapezoidal integration around argmax(abs(v)), zero endpoints, raw and normalized units | Author display normalization is unavailable |
| Realtime algorithm | `src/realtime_pipeline.py` | First prefix at L+B−1; future-shock invariance; receipt/event timestamps | Centered interior gradients with one-sided edges within an already available block |
| Equation 6, Tables 1–3 | `src/evaluation.py`, `src/benchmark.py` | Episode/event separation; 239/240 censoring, future-major and OOS-boundary regressions; independent recounts | Previous-target guard, major preference and recovery category are declared interpretations |
| Figure 1a–c | Exp1, `src/plotting.py` | Raw and envelope catalogs, separate SWH, raw-major markers, VIX = 35 line, histograms | Values depend on snapshot and FFT choice |
| Figure 2 | Exp2, `src/plotting.py` | Width, distance, skewness, kurtosis, CSV and KDE outputs | Grouping by future peaks is descriptive |
| Figure 3a–d | Exp3, `figure3_full_comparison` | Both scatter panels on common dates; envelope, potential, eigenvalue, High and gradient exports | Raw units; cutoff 74 is descriptive; no scaling to match the figure |
| Figure 4 | Exp4, realtime plotting | VIX, M, W, episodes and chosen catalog | Warning is available after session close, without backdating |
| Figure 5 | `lagged_gradient_correlation` | Known-lag test; −30…30 observations, pair counts, constant/insufficient status; 854 VSTOXX correlations checked independently | `corr(M[i], High[i+lag])`; positive means future High; descriptive correlation |
| Figure 6 | Exp5 | VXO, configured end-2004 split, preceding history and episode continuity | Fixed published threshold, no new calibration |
| Figure 7 | Exp6 | Fourteen real-data VSTOXX scenarios and saved ledgers | Partial High history; exact author OOS split unavailable |
| S1a/c/d | `aftershock_window`, `fit_omori_counts` | Fixed windows, nine starts, event exports, synthetic parameter-recovery and failure tests | Our aftershock and fitting interpretation; S1d R² differs and p reaches its bound |
| S1b | `log_index_decay` | OLS on global 1-based observation index; fixed 2008 window | Author origin/window unknown; a close descriptive regression is not independent evidence |
| S2 | `envelope_increment_diagnostics` | Lags 1/2/5/10/20, ddof = 0, 100 shared bins, density-integral checks | Bins and standardization are declared conventions |
| S3 | `run_paper_diagnostics`, `paper_plots` | VIX 2018/2020, C/M on receipt and event dates; repeated event dates retained | Calendar-year slices differ from the author's plot boundaries |
| S4 | Same modules | VXO 2020, W/threshold and M on both date axes | Event date is explanatory only |
| Tables S1–S3 | `load_paper_catalog`, `evaluate_catalog` | Ninety transcribed rows, hashes, event coverage and separate own/paper ledgers | Incomplete auxiliary flags are not filled by inference; missing dates are not shifted |
| Additional control | `compute_rolling_max_block` | Same envelope/coordinates; both boundaries and near-threshold disagreement tests | Not part of the paper; tests incremental value of eigenanalysis |
| Additional evaluation | `src/benchmark.py` | Alarm fraction, episode duration, lead distribution and 20/60/120/240 horizons | Main paper horizon remains 240 |

## Changes after review

Outcome cutoffs now apply during classification. Configuration is checked after overrides. Public runs preserve their inputs and provenance and reject nonempty output directories. Exp1–3 share descriptive work; Exp2–3 share eigenanalysis. Realtime filtering remains separate.

On a numerically flat inactive eigenvalue block, the diagnostic argmax selects the first coordinate when C = 0 and the block range is at most `64 * eps * max(1, max(abs(block)))`. M/C/W are unchanged. That coordinate is not evidence of physical localization on an unresolved flat block. Eighteen frozen reruns confirm unchanged event/episode tables and evaluation metrics.

## Boundaries of the evidence

The complete author input snapshots and normalization are unavailable. VSTOXX High only covers part of the author period. The author threshold-search history cannot be reconstructed. The equity panel, trading costs, portfolio construction and prospective forecasts are outside this replication.
