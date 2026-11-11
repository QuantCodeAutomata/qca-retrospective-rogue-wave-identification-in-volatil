# Real-time identification of financial rogue waves

A checked implementation of Hayward, Lennon and Biancalana, *Real-time identification of the onset of financial rogue waves*, arXiv:2606.31475v4.

**Status: partial numerical replication on real VIX, VXO and VSTOXX High data.** With `all_bins`, we detect 9/12 paper VIX events and 7/8 VXO events, matching the exact detected sets in the supplementary tables. Episode precision is 80.0% and 68.75%, versus 84.2% and 63.2% in the paper. The other FFT interpretation gives different results. Exact author settings and data snapshots are unavailable; forecasting performance is not established.

**VSTOXX.** The paper reports 7/8 major events detected and 70.6% episode precision. Our two longer High histories cover different subsets of those eight events. With `all_bins`, DAG (2010–2024) gives 3/4 detected and 60% precision, and Investing (2012–March 2025) gives 3/3 and 50%. With `spectral_peaks`, the same inputs give 3/4 and 100% on DAG, and 2/3 and 60% on Investing. [Results for all 14 VSTOXX scenarios](docs/REPLICATION.md#vstoxx).

The 11 November report adds a comdirect/Eurex daily High history from May 2005 through 10 November 2026. It covers six of the eight published VSTOXX major events. With a 240-observation horizon, `all_bins` detects 6/6 (10/15 useful episodes) and `spectral_peaks` detects 5/6 (7/8). These are new runs following the independent v2 review. [Updated judge report and all 14 figures](docs/judge_20261111/final_analysis_report.md).

[Paper on QCA](https://qca.limex.pro/file/f65a674b-d986-4fa5-a993-7c9e9ed49537--real-time-identification-of-the-onset-of-financial-rogue-waves) · [arXiv v4](https://arxiv.org/abs/2606.31475v4) · [Replication results](docs/REPLICATION.md) · [April 2025 / November 2026](docs/EVENT_STUDY.md) · [Article coverage](docs/ARTICLE_COVERAGE.md)

## What changed

The updated pipeline fixes evaluation cutoffs, validates the final CLI configuration, preserves input/configuration/code hashes, and refuses to overwrite existing runs. It adds per-event ledgers, separate paper and computed labels, endpoint censoring, horizon sensitivity, Figure 5 and S1–S4 diagnostics, and a same-envelope rolling-maximum control. Shared descriptive calculations are reused; realtime calculations still use only the available prefix.

The current code passes **216 tests**. Eighteen frozen scenarios were rerun after the review; event and episode tables and evaluation metrics were unchanged. Two further VIX runs cover data through 9 November 2026. Configurations, hashes, derived warning ledgers and receipts for all twenty runs are in [docs/evidence](docs/evidence/README.md). The old generated outputs, including synthetic VXO/VSTOXX results, were removed from the active tree; they remain in Git history at `d963cd2`.

## Install

Python 3.11+ is required by the pinned dependencies. Validation used Python 3.12.10.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -c constraints-validated.txt
python -m pytest tests -q
```

Runtime-only installation uses `requirements.txt`. `constraints-validated.txt` records tested direct dependency versions; it is not a complete transitive lockfile. Yahoo downloading is optional (`requirements-download.txt`). CSV calculations do not require it. Nothing downloads automatically.

## Run with real data

Supply a CSV with `date,high`, one observed session per row. Column names are case-insensitive and can be overridden. The input is daily **High in volatility-index points**, not Close or the underlying equity index. Invalid or duplicate dates and nonpositive/nonfinite High values fail. No missing weekdays are inserted and no synthetic fallback is used.

```bash
python run_experiments.py --index VIX --csv /path/to/VIX.csv \
  --end 2025-12-31 --filter-mode all_bins --labels both \
  --baseline rolling_max --paper-diagnostics --output results/vix_all_bins

python scripts/check_run.py --run results/vix_all_bins \
  --output results/vix_all_bins_check.json
```

Use a new output directory for each run. A complete run records its input, effective configuration, package versions, source/output hashes and completion status. `check_run.py` independently recounts the saved decisions, episode/event matches and metrics. It does not recalculate the envelope or eigenvalues.

The [official CBOE VIX CSV](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv) can be supplied with `--date-column DATE --high-column HIGH`. Its contents can change. The frozen input hashes in this repository identify our snapshots; a current download is not automatically an exact replay. The public repository includes derived results, not the full raw market-data archives. See [data provenance](docs/DATA.md).

| Option | Default | Meaning |
|---|---|---|
| `--index VIX\|VXO\|VSTOXX` | `VIX` | Volatility index |
| `--filter-mode spectral_peaks\|all_bins` | `spectral_peaks` | FFT interpretation |
| `--labels own\|paper\|both` | `own` | Separate calculated and published event catalogs |
| `--baseline rolling_max` | off | Same causal envelope, coordinates and thresholds |
| `--paper-diagnostics` | off | Figure 5 and applicable S1–S4 diagnostics |
| `--start`, `--end` | supplied sample | Inclusive observation bounds |
| `--insample-end` | index config | Evaluation split; retains earlier context |
| `--experiments` | `all` | 1–3 plus the index's realtime experiment |

Realtime experiments are 4 = VIX, 5 = VXO and 6 = VSTOXX. The previous experiment entrypoints remain available. VXO's configured in-sample cutoff is 31 December 2004. No VIX or VSTOXX holdout boundary is invented.

For a stored run, pass its `docs/evidence/runs/<run_id>/config.yaml` with `--config` and the appropriate input CSV. The manifest lists the selected experiments, actual dates, normalized input hash and original source hash. Full replay requires the matching input snapshot.

For a synthetic pipeline check only:

```bash
python run_experiments.py --demo --output results/synthetic_smoke
```

Synthetic output is marked throughout and has no replication meaning.

## Python API

```python
from run_experiments import run_project
from data.data_loader import load_config

config = load_config('VIX')
config.update(filter_mode='all_bins', labels='both', baseline='rolling_max')
run = run_project('VIX', highs, config=config, output_dir='results/python_run')
```

`highs` is a pandas Series indexed by observed session dates. The CLI and public experiment functions use the same input bounds, validation, provenance and overwrite guard.

## Numerical choices

The mirror is `[x, x[-2:0:-1]]`; Hilbert is applied before cropping. Descriptive experiments use the 92.5th percentile; realtime warnings and their calculated reference labels use the 95th. `spectral_peaks` takes the percentile over interior spectral maxima, while `all_bins` uses all one-sided amplitudes.

The operator is `H = -0.5 D2 - diag(envelope**2)`, with `dt = 1` and raw amplitudes. Default Dirichlet boundaries retain L−2 interior coordinates. The explicit `dirichlet_ghost` alternative retains all L coordinates. The author normalization and boundaries are not known.

Ten windows of L = 80 form each gradient block. M is its largest signed gradient, C counts gradients above 50, and W = M × C. The first eligible prefix contains 89 observations. All published thresholds remain fixed. The primary evaluation horizon is 240 observed sessions, with sensitivity at 20/60/120. Our matching conventions, including the previous-target guard, are described in the coverage matrix and tests.

A warning is available after its session's High is final. `event_date` is explanatory and may be earlier. Full-history peak labels are retrospective and can change with additional observations even when past warnings remain unchanged. Episodes crossing an evaluation split are not fired again. Unfinished outcome horizons are censored during classification, not relabeled by the metrics aggregator.

## Results and limits

The [replication report](docs/REPLICATION.md) separates detection counts, episode precision, input coverage and unresolved choices. The control produced identical binary alarms to QCA in the checked scenarios; this does not establish equality for all possible inputs or thresholds.

In April 2025, `all_bins` warned on 12 March and 7 April; `spectral_peaks` first warned on 10 April, after the paper's 8 April envelope peak. April is already in the paper and is not an independent VIX holdout. Both modes produced no warning in the available 2–9 November 2026 window. That selected case is a later-period retrospective check; its final rogue-wave label is still unresolved at the sample endpoint.

Supplement S1 is an explicit interpretation of an incomplete author protocol. Full author-period VSTOXX High, exact source snapshots, amplitude normalization and some computational choices remain unavailable. No trading strategy or prospective forecasting claim follows from these results.

See [LICENSE.md](LICENSE.md) for the repository's existing terms.
