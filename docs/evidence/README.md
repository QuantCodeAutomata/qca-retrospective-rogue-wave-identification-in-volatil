# Published evidence

This directory contains extracts from twenty completed runs: fourteen VSTOXX scenarios, four main VIX/VXO comparisons and two later VIX event-study runs. All forty-seven source files recorded by each original run match the published implementation byte for byte.

- [Run index](run_index.json): one record per run, with period, FFT mode and manifest path.
- `runs/<id>/manifest.json`: effective settings, source/input hashes, package versions, original manifest hash and hashes of the published outputs.
- `runs/<id>/config.yaml`: the effective configuration, accepted by `run_experiments.py --config`.
- `*_warning_data.csv`: derived M/C/W and receipt/event dates for QCA and the same-envelope control.
- `*_events_major.csv`: each major event, whether it was detected, associated useful episodes and first signal/lead.
- `*_signals_major*.csv`, `*_episodes.csv`: episode classifications and availability, including endpoint censoring.
- `*_evaluation.json`, `*_metrics.json`: own/paper results, horizon sensitivity, durations and alarm fraction. Filenames with `paper` refer to the fixed author catalog; filenames without it refer to calculated labels.
- [VSTOXX summary](run_summary.csv) and [VIX/VXO summary](vix_vxo_summary.csv): compact comparisons.
- [Independent VSTOXX checks](verification.json), [eighteen-run replay comparison](replay_comparison.json), [source rebuild](source_rebuild.json) and [event-study checks](event_independent_verification.json): saved validation receipts.

The original output names are retained. Some summary JSON files refer to plots or auxiliary tables available in the full offline bundle but not included here. These directories are explicitly evidence extracts, not complete managed runs: there is no input price CSV or `run_metadata.json`. Do not run `check_run.py` on an extract. It checks a complete new run or a full offline replay bundle.

The test log in `publication_pytest.txt` comes from the publication checkout. `publication_checks.json` records the source/evidence hash audit and CSV/JSON checks performed before publication. The original forty-seven-source manifest describes the computational snapshot, not the new documentation.

Run `python scripts/check_evidence.py` from the repository root to verify the published hashes and independently recount major-event metrics and baseline decisions. It uses only the Python standard library and does not need price inputs.

For an exact replay, obtain the matching input, select the stored configuration and experiments, and use a fresh output directory. The public repository supplies no hidden data access and does not fetch replacement input automatically.
