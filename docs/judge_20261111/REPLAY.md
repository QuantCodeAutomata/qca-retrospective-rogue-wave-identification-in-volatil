# Reproduce the 11 November figures

Run the project at revision `2ff88ad2f37af422dd0ddbb9706268058cea38b5` or the documentation commit containing this report. Both have the same QCA computational code. The report fixes its data endpoints at 10 November 2026 for VIX/VSTOXX and 23 September 2021 for VXO.

## Prepare the inputs

From the repository root, install the project dependencies as described in the README. The input helper also uses `xlrd==2.0.2` for the old CBOE XLS file. The checked environment was Python 3.12.10 with the repository’s direct dependency constraints.

```bash
python -m pip install 'xlrd==2.0.2'
python docs/judge_20261111/prepare_inputs.py --cache ./results/figure_sources \
  --output ./results/figure_inputs --download
```

With an existing raw cache, omit `--download`. The helper verifies all three normalized input hashes before writing outputs. A live source can change and CSV float conversion can differ by platform. A hash failure identifies a different snapshot or parse. The archived page URLs and raw hashes for comdirect are listed in [vstoxx_downloads.json](vstoxx_downloads.json). All three normalized inputs were reconstructed byte for byte from the archived raw files on the report machine.

| Prepared file | Source construction |
|---|---|
| VIX.csv | CBOE daily High through 10 Nov 2026. All 9,312 High values shared with the preceding day’s snapshot agree exactly when parsed with round-trip precision. |
| VXO_complete.csv | CBOE archive XLS and legacy CSV through 7 Jan 2021, followed by the 179 OHLC observations from the CBOE VXO chart from 8 Jan through 23 Sep 2021. The input keeps the original values on the overlap. |
| VSTOXX_comdirect.csv | 55 nonoverlapping pages of daily OHLC from comdirect, Eurex notation 12105800. Parsed using Latin-1, semicolons and decimal commas. Only observed session dates and published High values enter the calculation. |

## Regenerate the plots

Each command requires a new or empty output directory.

```bash
python run_experiments.py --index VIX --csv results/figure_inputs/VIX.csv \
  --experiments all --filter-mode all_bins --labels both --baseline rolling_max \
  --output results/figure_vix
python run_experiments.py --index VXO --csv results/figure_inputs/VXO_complete.csv \
  --experiments 1,5 --filter-mode all_bins --labels both --baseline rolling_max \
  --output results/figure_vxo
python run_experiments.py --index VSTOXX --csv results/figure_inputs/VSTOXX_comdirect.csv \
  --experiments 1,6 --filter-mode all_bins --labels both --baseline rolling_max \
  --output results/figure_vstoxx
```

The report uses the descriptive Exp1–3 images and each index’s `*_paper_warning.png`. The paper catalogs mark the target dates in the warning plots. The extension’s sensitivity checks use `--filter-mode spectral_peaks`, separate output directories, and experiments `1,4` (VIX), `1,5` (VXO) or `1,6` (VSTOXX). The effective configurations, row counts, ledgers for fixed major events, horizon scores, raw-source checks and hashes of the 14 delivered PNGs are in [evidence.json](evidence.json).

## Verify a run

```bash
python scripts/check_run.py --run results/figure_vstoxx --output results/figure_vstoxx_check.json
python -m pytest tests -q
```

The ledger checker recomputes episode arithmetic, verifies assignments and checks source/output hashes for that run. It does not depend on the old `compare_replay.py` script from the separate judge bundle. Image hashes identify the delivered figures. Different fonts, plotting libraries and environments can produce different PNG bytes for the same numeric series.
