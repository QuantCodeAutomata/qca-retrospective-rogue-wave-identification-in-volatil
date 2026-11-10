# What the replication establishes

We implemented and checked the calculations described in Hayward, Lennon and Biancalana, *Real-time identification of the onset of financial rogue waves*, arXiv:2606.31475v4 (15 October 2026). The result is a partial numerical replication. Several choices that affect the results are missing from the paper, and we do not have the authors' input snapshots.

## Method and evaluation

The input is daily High of a volatility index, in index points. The method mirrors the observed series, filters its Fourier spectrum, and takes the Hilbert envelope. The negative squared envelope becomes the potential of a discrete Schrödinger operator. Changes in its lowest eigenvalue produce the warning indicator, W = M × C. M is the largest signed gradient in a block of ten windows; C counts gradients above 50. Each window contains 80 observations. Warning thresholds are 300 for VIX/VSTOXX and 700 for VXO.

Each daily warning uses the history available at that date. It becomes available after that session's High is final. The explanatory `event_date` can be earlier; it is never the time at which the warning could have been acted on.

The reference events are retrospective envelope peaks. Significant wave height (SWH) is the mean of the largest third of peak prominences. A major wave has prominence greater than 2.5 SWH; the lower threshold is 2 SWH. These labels use future context and can change when the sample endpoint changes. We score against both our calculated labels and the paper's fixed catalog, separately.

The primary matching horizon is 240 observed sessions. A contiguous stretch above the warning threshold is one episode. Detection is the fraction of distinct major events with a useful episode. Precision is the fraction of warning episodes classified as useful detections. Several episodes can point to one event. Late and lower-event warnings do not count as useful major detections. Endpoint-censored precision excludes unresolved episodes from its denominator.

## VIX and VXO

These are full-sample scores against the paper's fixed major-event catalog. The VXO runs also export the separate 2005–2020 evaluation requested by the paper. The table below does not mix that OOS score with full-sample scores.

| Index / interpretation | Major events detected | Useful episodes / all episodes | Precision |
|---|---:|---:|---:|
| VIX, paper | 9/12 | 16/19 | 84.2% |
| VIX, `spectral_peaks` | 2/12 | 2/5 | 40.0% |
| VIX, `all_bins` | 9/12 | 16/20 | 80.0% |
| VXO, paper | 7/8 | 12/19 | 63.2% |
| VXO, `spectral_peaks` | 4/8 | 4/5 | 80.0% |
| VXO, `all_bins` | 7/8 | 11/16 | 68.75% |

VIX input spans 2 January 1990–31 December 2025; VXO spans 2 January 1986–31 December 2020. The VIX endpoint is our frozen comparison date, not a verified author endpoint. The authors' exact final observations are unavailable.

`spectral_peaks` estimates the filtering percentile from interior spectral maxima. `all_bins` uses all one-sided amplitudes. The latter comes closer to the published detection counts, but that agreement does not establish which procedure the authors used. Both modes remain available; no threshold or amplitude scale was fitted to these percentages.

See [the summary CSV](evidence/vix_vxo_summary.csv) and the [run index](evidence/run_index.json) for configurations, input hashes, warning ledgers and per-event results.

## VSTOXX

We ran fourteen fixed scenarios across two partial High histories, their common dates, a calendar sensitivity check, alternate boundaries and a short sample. No source covers the full author period.

| Input / FFT | Observations | Covered paper major events | Precision |
|---|---:|---:|---:|
| DAG, `spectral_peaks` | 3,626 | 3/4 | 100% (4/4 episodes) |
| DAG, `all_bins` | 3,626 | 3/4 | 60% (3/5) |
| Investing, `spectral_peaks` | 3,117 | 2/3 | 60% (3/5) |
| Investing, `all_bins` | 3,117 | 3/3 | 50% (3/6); 60% excluding one unresolved episode |

DAG spans 3 September 2010–22 November 2024. Investing spans 28 December 2012–28 March 2025. Their labels are source identifiers, not a claim that the exports equal an official author snapshot. The paper reports 7/8 major events and 70.6% precision over a longer period; comparing that directly with 3/3 or 3/4 would change the denominator.

On the shared 3,032 dates, event detection agrees between sources within each FFT mode. A few daily decisions still differ. Removing six dates without matching records in a comparison Close series changes one precision result from 60% to 50%. Missing Close records do not prove those dates were invalid index sessions. Changing the boundary convention reduces DAG `spectral_peaks` detection from 3/4 to 2/4. The 90-row Portara sample supplies only two eligible warning dates and cannot support a performance estimate.

All scenarios are retained in [run_summary.csv](evidence/run_summary.csv), including weak or unavailable results. The fixed 240-session horizon also matters: one Investing detection links an August 2015 signal to a June 2016 event, 208 observations later. Its 3/3 detection falls to 2/3 at horizons of 20, 60 or 120 observations.

## Controls and checks

The control replaces the eigenvalue calculation with the maximum squared value of the same causal envelope on the same retained coordinates. It keeps the gradients, thresholds and evaluation rules. In the fourteen VSTOXX scenarios it produces the same binary warning decisions on all 38,036 evaluated rows. These rows include overlapping scenarios, not 38,036 independent dates. The numerical indicators differ. The result does not prove equivalence under other scales, inputs or thresholds, but it does not show added detection value from the eigenvalue step in this experiment.

In all twelve long VSTOXX scenarios, the largest tested correlation between M and High occurs at lag −1 or −2. Positive lag means future High. This descriptive correlation does not establish advance prediction.

The code passes 216 tests, including the original 128 checks. Tests cover mathematical references, future-prefix invariance, signal availability, endpoint censoring, configuration errors, baseline boundaries and supplement calculations. Independent VSTOXX evaluation made 261,914 ledger/metric comparisons and checked 854 lagged correlations. All passed.

After the judge review, eighteen runs were repeated with the current code. All 562 compared event/episode/horizon tables and 112 metric/evaluation JSON files were unchanged. The only warning-table changes were diagnostic locations for numerically flat inactive blocks: C = W = 0 and |M| ≤ 1e−8. M, C and W were not rounded or changed. Counts in the [receipt](evidence/replay_comparison.json) include repeated exports of the same rows.

## What remains unresolved

The authors' amplitude normalization, exact input snapshots, FFT details, boundary conditions and some matching rules are not fully specified. We use raw index points and explicit alternatives. Scaling the input to match a figure or percentage would change the experiment.

Supplement S1 is a declared interpretation. Its horizons and aftershock definition were fixed before fitting. S1b closely matches the reported regression under that interpretation. S1d gives R² = 0.9341 versus 0.895 in the paper, with p at its upper bound of 3. S3 uses calendar-year slices, which differ from the exact plot windows in the paper. Implementing all panels therefore does not establish exact reproduction of all supplementary results.

The frozen runs establish reproducibility of this implementation. They do not establish prospective forecasting performance, a profitable trading strategy, or numerical identity with the authors' method. The [April 2025 and November 2026 case study](EVENT_STUDY.md) makes the distinction between peak detection and timely warning concrete.
