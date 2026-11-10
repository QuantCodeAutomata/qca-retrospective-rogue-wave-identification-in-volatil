# April 2025 and November 2026

We applied the frozen protocol to official CBOE daily VIX High through 9 November 2026: 9,312 observations from 2 January 1990. Each FFT mode produced 9,224 warning rows. Parameters were unchanged. VIX is the algorithm input; S&P 500 prices provide context only. Applying these thresholds directly to the SPX price level would be a different experiment.

## April 2025

The paper's Table S1 lists the VIX envelope peak on 8 April 2025, with first signals on 11 March and 7 April.

| FFT interpretation | First available signals | Relative to the paper's 8 April peak |
|---|---|---|
| `all_bins` | 12 March: W = 306.13; 7 April: W = 546.11 | 19 and 1 observed sessions early |
| `spectral_peaks` | 10 April: W = 495.60 | 2 sessions late |

The March `all_bins` episode lasts one session and is only slightly above the threshold of 300. Its April episode lasts through 17 April. The `spectral_peaks` episode lasts through 16 April. Relative to the paper, the March signal is one session later and the 7 April signal agrees.

The S&P 500 had already fallen 4.84% on 3 April and another 5.97% on 4 April. Raw VIX High reaches 60.13 on 7 April. A warning available after that session is earlier than the smoothed envelope peak on 8 April, but it did not precede the start of the selloff. The March signal did precede it; one retrospectively matched case is insufficient to establish forecasting skill.

April 2025 is included in the paper's analysis. The paper describes repeated threshold selection for VIX and does not establish a separate VIX holdout. This event must not be presented as an independent out-of-sample test of the paper. We cannot establish which specific dates influenced each author calibration attempt.

## November 2026

The S&P 500 fell 4.36% on 5 November. The official CBOE table gives VIX High = 28.36 and Close = 28.18. Both FFT modes produced W = 0 throughout 2–9 November. On 5 November, M was 18.16 for `spectral_peaks` and 40.17 for `all_bins`, below the gradient-count threshold of 50; C was zero.

There was no warning for this selloff in the available window. However, there were only two observations after 5 November, and the available envelope did not yet establish a major rogue peak. Prominence requires subsequent context. We therefore do not count this as a proven missed major event in the catalog score.

November is after the paper and after our parameter freeze. The case was selected after the event, so it is a retrospective check on a later period, not a preregistered prospective evaluation.

## Checks and sample dependence

Independent code recomputed 98 daily prefixes and 980 dense matrices. Maximum differences were 2.84e−12 for M and 1.05e−11 for W; all C values and warning decisions agreed. In each mode, all 9,003 warning rows through the end of 2025 agreed with the previous frozen run within rtol = 1e−10 and atol = 1e−8.

QCA and the same-envelope `rolling_max` control agreed on all 18,448 binary decisions across the two modes. This is two calculations over 9,224 dates, not 18,448 independent sessions.

Adding observations left past warnings unchanged but changed a retrospective label: the April `spectral_peaks` wave was lower on the December 2025 snapshot (prominence/SWH = 2.414) and major on the November 2026 snapshot (2.559). Causal signals and full-history target labels have different availability.

These cases show sensitivity to the FFT interpretation and no response to the selected November selloff at the published thresholds. They do not supply a statistical estimate of general forecasting performance.

## Evidence and replay

- [Frozen study plan](evidence/event_study_plan.json)
- [Independent calculation receipt](evidence/event_independent_verification.json)
- [Peak-label snapshots](evidence/peak_label_snapshots.csv)
- [All-bin ledgers and configuration](evidence/runs/vix_2026_all_bins/)
- [Spectral-peak ledgers and configuration](evidence/runs/vix_2026_spectral_peaks/)
- [Official CBOE source](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv)

The raw download was retrieved on 10 November 2026 at 15:32 UTC, SHA-256 `0fbd2010663102746b54b12bf96ab0ca4add0c922aebc4dabb0a84cd9c8b0e63`. The live endpoint may change. The normalized input hash and effective configuration are in each run's public manifest. Raw OHLC and complete replay bundles are retained separately; this repository contains derived ledgers and evidence extracts.

To rerun from a supplied CSV, choose a fresh output directory for each mode:

```bash
python run_experiments.py --index VIX --csv /path/to/VIX.csv \
  --end 2026-11-09 --experiments 1,4 --filter-mode all_bins \
  --labels both --baseline rolling_max --output results/events_all_bins
python scripts/check_run.py --run results/events_all_bins \
  --output results/events_all_bins_check.json
```

Repeat with `--filter-mode spectral_peaks` and a different output directory. A current CBOE file can be supplied directly with `--date-column DATE --high-column HIGH`; matching the old input hash is required for an exact replay.
