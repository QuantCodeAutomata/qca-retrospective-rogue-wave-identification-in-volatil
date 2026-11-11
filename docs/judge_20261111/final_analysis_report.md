# FINAL RESULTS ANALYSIS

## Executive Summary

- **Status:** **PARTIALLY REPRODUCED**
- **Confidence:** **HIGH**
- **Key Insight:** Using real daily High data and the `all_bins` filter, QCA detected exactly the same major events as the authors for **VIX (9/12)** and **VXO (7/8)**. The independent judge confirmed the identities of the missed events as well. Episode precision, first-warning dates and the event catalogs built from scratch differ. On the longer VSTOXX series, six of the eight published events fall within the available history.

---

## Repository Result Content Reviewed

The independent judge reviewed the 10 November 2026 package against Hayward, Lennon and Biancalana’s *Real-time identification of the onset of financial rogue waves*. The review covered **21 historical runs** (seven VIX/VXO and fourteen VSTOXX). The six additional runs on 11 November supplied the figures in this report. [Paper, arXiv v4](https://arxiv.org/abs/2606.31475v4) · [Reviewed implementation](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/tree/2ff88ad2f37af422dd0ddbb9706268058cea38b5)

- [Historical results, configurations and warning logs](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/REPLICATION.md)
- [Published event tables and source hashes](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/tree/main/verification/source_evidence)
- [11 November numerical results, input hashes and figure hashes](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/judge_20261111/evidence.json)
- [Commands to rebuild the inputs and figures](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/judge_20261111/REPLAY.md)

All fourteen figures use real daily High and the `all_bins` filter. We also ran `spectral_peaks` for each index. The latest completed session at the time of the refresh was 10 November 2026.

- **VIX:** 9,313 CBOE observations, 2 January 1990 – **10 November 2026**. Last High **21.61**. The judge’s comparison ends on 31 December 2025. [CBOE historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data)
- **VXO:** 8,998 CBOE observations, 2 January 1986 – **23 September 2021**, when publication ended. Last High **18.63**. The judge’s comparison ends on 31 December 2020. [CBOE chart feed](https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/_VXO.json) · [Discontinued series](https://fred.stlouisfed.org/series/VXOCLS)
- **VSTOXX:** 5,442 comdirect/Eurex observations, 26 May 2005 – **10 November 2026**. Last High **19.0829**. The judge checked the earlier DAG and Investing histories separately. [comdirect spot index](https://www.comdirect.de/inf/indizes/DE000A0C3QF1) · [55 download pages and hashes](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/judge_20261111/vstoxx_downloads.json)

---

## Results Comparison

### Experiment 1 — Retrospective Rogue-Wave Identification

This experiment asks whether the processed envelope has fewer local peaks than raw High, which crisis peaks survive filtering, and how many qualify as extremes. Each series has its own significant wave height (SWH), the mean of the largest third of its peak prominences, with the count rounded up.

### Reproduced results

| Metric | Paper / Expected | Reproduced | Diff | Status |
|--------|------------------|------------|------|--------|
| Fewer local peaks after filtering | Yes | All three indices | Same direction | ✅ |
| VIX peaks in the 1998, 2008 and 2020 crises | Yes | All three present | Same crisis years | ✅ |
| Major-event dates reconstructed from High | Published VIX and VXO dates | 7/12 VIX and 3/9 VXO dates match exactly in the frozen runs | Partial overlap | ⚠️ |
| Separate VXO and VSTOXX analyses | Real index High | CBOE VXO and comdirect VSTOXX | Early VSTOXX history unavailable | ⚠️ |

#### Key reproduced numbers

The figures and counts below use the refreshed samples and the 92.5th-percentile descriptive filter. “Lower Extremes” counts only peaks above 2×SWH that did not qualify as major. Raw High and the envelope use separate SWH values.

| Index | SWH | Major Peaks (>2.5×SWH) | Lower Extremes (>2×SWH) | Envelope Peaks | Raw Peaks |
|------|-----:|------------------------:|-------------------------:|---------------:|----------:|
| VIX | 7.1408 | 15 | 4 | 703 | 2,294 |
| VXO | 8.0012 | 14 | 5 | 734 | 2,251 |
| VSTOXX | 7.7716 | 8 | 7 | 466 | 1,339 |

#### VIX major peak dates recovered

The full-history VIX envelope through 10 November 2026 marks these 15 dates as major:

- 1991-01-14
- 1997-10-29
- 1998-10-07
- 2001-09-19
- 2002-07-23
- 2008-10-13
- 2010-05-20
- 2011-08-09
- 2015-08-25
- 2018-02-06
- 2018-12-24
- 2020-03-16
- 2022-10-10
- 2024-08-05
- 2025-04-08

### Summary

**Exp1 is reproduced qualitatively.** The VIX envelope retains the large crisis peaks and has 703 local peaks compared with 2,294 in raw High. Its retrospective dates depend on the sample endpoint. Experiments 4–6 score warnings against the fixed dates published in the paper.

### Figures

![VIX envelope overlay](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp1_VIX_envelope_overlay.png)

![VIX prominence histogram](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp1_VIX_histogram_prominences.png)

![VIX raw histogram](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp1_VIX_histogram_raw.png)

![VXO envelope overlay](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp1_VXO_envelope_overlay.png)

![VSTOXX envelope overlay](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp1_VSTOXX_envelope_overlay.png)

---

### Experiment 2 — Retrospective Localization and Schrödinger Eigenanalysis

The expected result is a narrower lowest-eigenvalue eigenvector, with its maximum closer to the end of the window as a major VIX peak approaches.

### Reproduced results

The values run from windows more than 30 observations before the next peak to windows one to five observations before it.

| Metric | Paper / Expected | Reproduced | Diff | Status |
|--------|------------------|------------|------|--------|
| Width decreases near peaks | Yes | 0.1525 → 0.0805 → 0.0163 | Same direction | ✅ |
| Distance to window end decreases | Yes | 42.92 → 26.91 → 10.12 | Same direction | ✅ |
| Potential skewness becomes more negative | Yes | −0.561 → −0.780 → −1.657 | Same direction | ✅ |
| Potential excess kurtosis rises | Yes | −0.056 → 0.381 → 4.408 | Same direction | ✅ |
| Distributions overlap | Yes | Visible in all four plots | Qualitative match | ✅ |

#### Reproduced summary table

| Bin (observations to next major peak) | n | Width Mean | Distance Mean | Skewness Mean | Kurtosis Mean |
|---|---:|---:|---:|---:|---:|
| 1–5 | 75 | 0.0163 | 10.12 | −1.657 | 4.408 |
| 6–30 | 375 | 0.0805 | 26.91 | −0.780 | 0.381 |
| >30 | 8,358 | 0.1525 | 42.92 | −0.561 | −0.056 |

The grid spacing is one observation. A further 426 windows fell on a peak date or after the last known peak and could not be assigned to a group.

### Summary

**Exp2 is reproduced qualitatively.** All four group means move in the direction shown in the paper. The groups depend on knowing the next peak, and their distributions overlap.

### Figures

![VIX width KDE](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp2_VIX_width_kde.png)

![VIX localization distance KDE](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp2_VIX_loc_distance_kde.png)

![VIX skewness KDE](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp2_VIX_skewness_kde.png)

![VIX kurtosis KDE](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp2_VIX_kurtosis_kde.png)

---

### Experiment 3 — Minimum-Eigenvalue-Gradient Analysis

The paper plots the signed gradient of the magnitude of the lowest eigenvalue against the time to the next major VIX peak. Figure 3 compares that gradient with the squared-envelope gradient and illustrates a cutoff near 74.

### Reproduced results

- Total windows: **9,234**
- Maximum signed gradient: **493.42**
- Observations with gradient > 74: **118**
- Observations with gradient > 100: **83**

| Metric | Paper / Expected | Reproduced | Diff | Status |
|--------|------------------|------------|------|--------|
| Gradient relative to the next major peak | Scatter by time to peak | Plotted on the observed calendar | Comparison is retrospective | ✅ |
| Illustrative VIX cutoff around 74 | Large positive gradients cross 74 | 118 windows exceed 74 | Descriptive threshold | ✅ |
| Eigenvalue, potential and squared-envelope panels | Figure 3a–d | Four panels in source units | Author display normalization unknown | ⚠️ |

### Summary

**Exp3 reproduces the qualitative gradient comparison.** The published amplitude normalization is unknown, which limits a point-for-point comparison of the panels. The count above 74 measures historical exceedances.

### Figures

![VIX gradient vs days to next peak](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp3_VIX_grad_vs_days.png)

![VIX gradient comparison](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp3_VIX_gradient_comparison.png)

---

### Experiment 4 — Simulated Real-Time Rogue-Wave Warning Indicator on VIX

Detection counts distinct paper events reached by at least one warning episode within 240 observed sessions. Precision divides useful episodes by all evaluated episodes. Several episodes can precede the same event. Late warnings, warnings associated with lower events and false signals have separate categories.

#### Paper targets

For **major peaks** (>2.5×SWH):

- Peaks detected: **9/12 (75.0%)**
- False signals: **0%**
- Precision: **16/19 (84.2%)**
- Precision excluding late signals: **94.1%**

For the **lower threshold** (>2×SWH):

- Peaks detected: **9/15 (60.0%)**
- False signals: **0%**
- Precision: **84.2%**
- Precision excluding late signals: **100%**

#### Reproduced results

The frozen `all_bins` comparison covers January 1990 through December 2025. Differences are percentage points relative to the paper’s published percentages, at their stated precision. [VIX evaluation](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/evidence/runs/vix_2025_all_bins/exp4_vix_paper_evaluation.json)

| Metric | Paper | Reproduced | Diff | Status |
|--------|-------|------------|------|--------|
| Peaks detected % (>2.5×SWH) | 75.0 | 75.0 (9/12) | 0.0 | ✅ Same events |
| False signals % (>2.5×SWH) | 0.0 | 0.0 | 0.0 | ✅ |
| Precision % (>2.5×SWH) | 84.2 | 80.0 | −4.2 | ⚠️ |
| Precision excl. late % (>2.5×SWH) | 94.1 | 94.1 | 0.0 | ✅ |
| Peaks detected % (>2×SWH) | 60.0 | 60.0 (9/15) | 0.0 | ✅ Same count |
| False signals % (>2×SWH) | 0.0 | 0.0 | 0.0 | ✅ |
| Precision % (>2×SWH) | 84.2 | 80.0 | −4.2 | ⚠️ |
| Precision excl. late % (>2×SWH) | 100.0 | 100.0 | 0.0 | ✅ |

#### Additional operational counts

- **20 warning episodes** at the major threshold: 16 useful, three late, one associated with a lower event, zero classified as false.
- **Three missed major events**, identical to the paper: 28 October 1997, 2 September 1998 and 6 February 2018.
- With `spectral_peaks`, detection falls to **2/12** and precision to **2/5**.

The paper lists 8 April 2025 as a VIX peak. Our `all_bins` warnings came on 12 March and 7 April, 19 and one observed sessions before the peak. The authors list 11 March and 7 April. The April warning followed the S&P 500 declines on 3–4 April. The first `spectral_peaks` warning arrived on 10 April. April 2025 falls within the paper’s development and evaluation history.

For the November 2026 selloff, both filters gave **W = 0** on every observed date from 2 through 10 November. Only three further sessions had elapsed since 5 November. Its retrospective event label remains provisional. [Event study](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/EVENT_STUDY.md)

### Summary

**Exp4 is partially reproduced quantitatively.** The detected major events agree exactly. The paper reports 19 episodes and our implementation finds 20. Extending the figure to 10 November 2026 preserved the binary decisions and M/C/W within numerical tolerance on all 9,003 common VIX rows in each filter mode.

### Figure

![VIX warning indicator](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp4_vix_paper_warning.png)

---

### Experiment 5 — Real-Time Warning Indicator on VXO

#### Paper targets

For **major peaks**, Table 2 reports **7/8 (87.5%)** detected, **15.8%** false signals, **63.2%** precision (12/19 episodes) and **66.7%** precision excluding late signals.

For the **lower threshold**, the corresponding figures are **10/13 (76.9%)**, **15.8%**, **73.7%** and **82.4%**. Table 2 covers the full series. Four of its eight major events fall in the 2005–2020 holdout.

#### Reproduced results

The independent judge checked the CBOE history from January 1986 through December 2020. The chart adds the final months of VXO publication in 2021. [VXO evaluation](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/evidence/runs/vxo_2020_all_bins/exp5_vxo_paper_evaluation.json)

##### Full sample

| Metric | Paper | Reproduced | Diff | Status |
|--------|-------|------------|------|--------|
| Peaks detected % (>2.5×SWH) | 87.5 | 87.5 (7/8) | 0.0 | ✅ Same events |
| False signals % (>2.5×SWH) | 15.8 | 18.75 | +2.95 | ⚠️ |
| Precision % (>2.5×SWH) | 63.2 | 68.75 | +5.55 | ⚠️ |
| Precision excl. late % (>2.5×SWH) | 66.7 | 68.75 | +2.05 | ⚠️ |
| Peaks detected % (>2×SWH) | 76.9 | 69.23 (9/13) | −7.67 | ⚠️ One fewer event |
| False signals % (>2×SWH) | 15.8 | 18.75 | +2.95 | ⚠️ |
| Precision % (>2×SWH) | 73.7 | 75.0 | +1.30 | ⚠️ |
| Precision excl. late % (>2×SWH) | 82.4 | 80.0 | −2.4 | ⚠️ |

Of the 16 major-threshold episodes, 11 were useful, three were classified as false and two were associated with lower events. The only missed major was **24 May 2010**, also missed in the paper. With `spectral_peaks`, the result falls to **4/8** detected with **4/5** useful episodes.

##### Out-of-sample major peaks

| Metric | Paper / Expected | Reproduced | Diff | Status |
|--------|------------------|------------|------|--------|
| Major events detected, 2005–2020 | 3/4 marked detected in Table S2 for these dates | 3/4 (75.0%) | Same four dates and same miss | ✅ |
| False signals % | Table 2 gives the full-series rate | 14.29 (1/7) | Separate holdout rate | — |
| Precision % | Table 2 gives the full-series rate | 57.14 (4/7) | Separate holdout rate | — |
| Precision excl. late % | Table 2 gives the full-series rate | 57.14 (4/7) | Separate holdout rate | — |

### Summary

**Exp5 is partially reproduced quantitatively on real VXO High.** The seven detected major events match, including which event was missed. Episode counts and precision differ. The holdout covers four major events. [Supplementary Table S2 transcription](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/verification/source_evidence/paper_VXO_supplement_table.csv)

### Figure

![VXO warning indicator](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp5_vxo_paper_warning.png)

---

### Experiment 6 — Real-Time Warning Indicator on VSTOXX

#### Paper targets

For **major peaks**, Table 3 reports **7/8 (87.5%)** detected, **11.8%** false signals, **70.6%** precision (12/17 episodes) and **80.0%** precision excluding late signals. The authors missed **21 June 2016**.

For the **lower threshold**, the corresponding figures are **8/9 (88.9%)**, **11.8%**, **76.5%** and **86.7%**.

#### Reproduced results

The **11 November comdirect run** covers six of the eight published major events and seven of the nine lower-threshold events. The 2001 and 2002 events predate the input. The table gives the `all_bins` results alongside the full-paper targets. A percentage-point difference would combine different periods and denominators.

| Metric | Paper | Reproduced | Diff | Status |
|--------|-------|------------|------|--------|
| Peaks detected % (>2.5×SWH) | 87.5 (7/8) | 100.0 (6/6 covered) | Two dates outside the input | ⚠️ Partial history |
| False signals % (>2.5×SWH) | 11.8 | 6.7 (1/15) | Different periods | ⚠️ |
| Precision % (>2.5×SWH) | 70.6 | 66.7 (10/15) | Different periods | ⚠️ |
| Precision excl. late % (>2.5×SWH) | 80.0 | 83.3 (10/12) | Different periods | ⚠️ |
| Peaks detected % (>2×SWH) | 88.9 (8/9) | 100.0 (7/7 covered) | Two dates outside the input | ⚠️ Partial history |
| False signals % (>2×SWH) | 11.8 | 6.7 (1/15) | Different periods | ⚠️ |
| Precision % (>2×SWH) | 76.5 | 73.3 (11/15) | Different periods | ⚠️ |
| Precision excl. late % (>2×SWH) | 86.7 | 91.7 (11/12) | Different periods | ⚠️ |

The source and filter both matter:

- **Judge v2, DAG (2010–2024):** `all_bins` detected **3/4**, with **3/5** useful episodes (60%). `spectral_peaks` also detected **3/4**, with **4/4** useful episodes (100%).
- **Judge v2, Investing (2012–March 2025):** `all_bins` detected **3/3**, with **3/6** useful episodes (50%), or **3/5** (60%) after excluding one unresolved episode. `spectral_peaks` detected **2/3**, with **3/5** useful episodes (60%).
- **11 November, comdirect (2005–2026):** `all_bins` detected **6/6**, with **10/15** useful episodes (66.7%), or **10/14** (71.4%) after excluding one unresolved episode. `spectral_peaks` detected **5/6**, with **7/8** useful episodes (87.5%). Those five detected dates match the authors’ detections on the same six dates.

On Investing, the only episode assigned to 21 June 2016 began on 26 August 2015, **208 observations earlier**. Detection falls from 3/3 at 240 observations to 2/3 at 20, 60 or 120. On comdirect, `all_bins` had two qualifying episodes for that event, on 27 August 2015 (207 observations early) and 20 June 2016 (one early). The 2016 event survives the 20-observation horizon on comdirect, where overall detection falls to 5/6.

### Summary

**Exp6 is partially reproduced on the covered dates.** The comdirect history adds two paper events to the DAG comparison. It also extends the warning series beyond the last published event. Precision depends on which events and warning episodes the chosen period includes.

### Figure

![VSTOXX warning indicator](https://raw.githubusercontent.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/main/docs/judge_20261111/figures/exp6_vstoxx_paper_warning.png)

---

## Statistical & Economic Significance

### Statistical significance

- **Exp1–Exp3:** The peak counts, localization means and gradient plots describe the observed samples. The reproduction supplies no confidence intervals or hypothesis test for the differences between peak groups.
- **Exp4–Exp6:** The judge independently confirmed the fixed-catalog event assignments. Precision changes with the source, filter and matching horizon. Scenarios share dates and observations.
- **Figure 5:** With positive lag defined as future High, the maximum correlation occurs at −1 or −2 observations in twelve long VSTOXX scenarios and at −4 for VXO `spectral_peaks`. These correlations do not estimate incremental forecasting accuracy.

### Economic significance

- The matched `rolling_max` control produced the same binary warnings as the eigenvalue method in **99,971 paired rows** across the 21 historical scenarios. We independently recounted the saved rows. The six refreshed runs also agreed in **46,978 paired rows**. Continuous M and W differ.
- The April 2025 VIX example distinguishes detection of an envelope peak from an alert before the equity decline. Prospective value would require a prespecified period and comparison methods. A trading result would also require executable prices after the daily High becomes known and transaction costs.

---

## Discrepancies

### 1. Historical source coverage

The judge’s expanded package includes the previously missing VIX/VXO inputs and daily warning logs. VSTOXX High still begins after the 2001 and 2002 events. The authors’ exact snapshots remain unavailable.

The comdirect extract identifies the Eurex quotation of the VSTOXX spot index, ISIN DE000A0C3QF1. Its 55 pages contain unique dates, positive High and internally consistent OHLC. The extract lacks 23 dates in the official STOXX Close history. Close differs by more than 0.01 on nine shared dates, and High is below the official Close by more than 0.01 on three. Within 0.01 point, 3,597 of 3,604 High values agree with DAG and all 90 agree with Portara. The vendors may share upstream data. [Official STOXX Close](https://www.stoxx.com/document/Indices/Current/HistoricalData/h_v2tx.txt)

### 2. First warnings and episode precision

The frozen VIX run has **16/20** useful episodes compared with **16/19** in the paper. VXO has **11/16** compared with **12/19**. Matching the distinct major events does not fix the number or timing of episodes associated with each event.

### 3. Published events and reconstructed catalogs

Using `all_bins` on each frozen history, **seven of twelve** QCA major VIX dates and **three of nine** QCA major VXO dates exactly match the published catalog. The paper lists eight major VXO events. The Exp4 and Exp5 event identity results use that published catalog as the reference.

### 4. Sample endpoint differences matter

In the judge’s VIX extension from 2024 to 2025, all **8,745** shared W values agreed. One historical envelope peak moved from 4 to 8 September 1998. Daily signals use only the history available at each date. The retrospective envelope, SWH and peak dates depend on the full selected series.

For the VXO chart we retained the historical archive through 7 January 2021 and appended 179 daily High values. Of 7,029 overlapping dates, 90 High values differ by more than 0.01 point between the two CBOE feeds, with a maximum difference of 10.01. [CBOE archive](https://www.cboe.com/tradable-products/vix/vix-historical-data)

### 5. FFT, boundaries and supplementary results

- Changing the FFT percentile population changes 67 historical daily VIX warning decisions and 63 VXO decisions. Moving the zero boundary values just outside the window changes 14 VIX and 13 VXO decisions under `all_bins`.
- In S1b, VIX `spectral_peaks` gives slope **−18.217**, intercept **158.386** and **R² = 0.9298**, close to the paper’s −18.2, 158.4 and 0.93.
- In S1d (2011), **R² = 0.9341** compared with **0.895** in the paper. The fitted exponent reaches the upper bound **p = 3**. The authors’ aftershock and fitting details remain unknown. The S3 calendar-year windows also differ from those shown in the paper. [Supplement protocol](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/SUPPLEMENT_PROTOCOL.md)

---

## Methodology Issues

1. **Input and filter.** The code mirrors daily High, filters the Fourier spectrum, applies the inverse transform and calculates the Hilbert envelope. The descriptive filter uses the 92.5th percentile and the daily warning filter uses the 95th. `all_bins` sets the cutoff from all one-sided amplitudes, `spectral_peaks` from their interior local maxima. The authors’ amplitude normalization is unspecified. QCA retains the original index units.

2. **Warning calculation.** The potential is the negative squared envelope. In ten consecutive windows of 80 observations, M is the largest signed gradient of the magnitude of the lowest eigenvalue. C counts gradients above 50. W = M × C must exceed 300 for VIX/VSTOXX or 700 for VXO. Each signal becomes available once that day’s High is final. Consecutive days above threshold form one episode.

3. **Control and scale.** The control takes the rolling maximum of the same squared causal envelope on the same retained coordinates. At grid spacing 1 with a negative minimum eigenvalue, the judge derived **0 ≤ max(envelope²) − |λmin| ≤ 1**. The bound explains the closeness of the two values in index units. Agreement after applying the gradient and warning threshold was measured in the runs.

4. **Author reference needed.** A worked example for one date, containing the High history, normalized envelope, ten eigenvalues and M/C/W, would distinguish the filter, scale and boundary choices. Rebuilding the catalogs also requires the authors’ event-date and episode rules. [Article coverage](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/ARTICLE_COVERAGE.md)

---

## Reliability

### Strengths

- The independent judge verified **3,085 manifest entries**, rechecked **3,086 files**, ran **216 tests** and independently reconstructed episodes and event assignments for **all 21 historical scenarios**.
- The judge recalculated **82 selected prefixes and 820 spectral matrices**. The detected VIX/VXO major-event identities agree with the supplementary tables.
- For the 11 November runs, all **216 repository tests** passed. An independent ledger checker passed on all six runs. Dense-matrix checks of **28 additional prefixes and 280 matrices** agreed on C and all alarm decisions. The largest absolute W difference was below **4 × 10⁻¹⁰**. [Numerical checks](https://github.com/QuantCodeAutomata/qca-retrospective-rogue-wave-identification-in-volatil/blob/main/docs/judge_20261111/evidence.json)

### Red flags

- The judge’s `compare_replay.py` stopped on an inactive DAG plateau on 21 December 2011. The maximizing offset changed from 2 to 3 and the diagnostic date from 12 to 13 December, with C = W = 0. The checker required the new offset to be zero. The existing flat-block rule misses a descending block that ends in a plateau.
- CSV parsing differed by one unit in the last place on **four VIX and 28 VXO observations** across environments. This changed input fingerprints. The tested warnings and metrics agreed. The VIX source also reports identical OHLC for all **505 records in 1990–1991**, with some inconsistent High values elsewhere.
- Signal dates, normalization, early VSTOXX coverage and supplementary fitting details limit a full numerical comparison.

### Overall confidence

- **High** in the partial-replication verdict and the exact VIX/VXO detected-event sets under `all_bins` with the paper catalog.
- **Qualitative agreement** for retrospective localization and gradients. The author scale remains unknown.
- **Partial coverage** for VSTOXX. The judge’s DAG and Investing checks and our later comdirect results use different histories.
- **Open** for prospective forecasting gains and trading performance.

---

## Verdict

**Final Decision: PARTIALLY REPRODUCED**

### Why

The independent review confirms three findings:

- The descriptive envelope isolates the large VIX peaks, and localization strengthens as a retrospectively identified peak approaches.
- Against the published catalog, `all_bins` recovers the exact major-event detection sets for VIX and VXO.
- On the covered VSTOXX dates, outcomes depend on the input, FFT convention and matching horizon.

First-warning dates, episode counts, reconstructed catalogs and part of the supplementary results still differ. The agreement with `rolling_max` limits the measured contribution of the eigenvalue step to binary alarms on these samples. **Confidence in the partial replication is high.**

---

## Per-Experiment Bottom Line

| Experiment | Decision | Notes |
|-----------|----------|-------|
| Exp1 | **Reproduced qualitatively** | Fewer peaks after filtering in all three real indices. Some reconstructed major-event dates differ. |
| Exp2 | **Reproduced qualitatively** | The eigenvector narrows and moves toward the window end as a major VIX peak approaches. |
| Exp3 | **Reproduced qualitatively** | Signed gradients and all four panels are available. The author normalization remains unknown. |
| Exp4 | **Partially reproduced quantitatively** | VIX matches the same 9/12 major events. Episode precision is 80.0% versus 84.2%. |
| Exp5 | **Partially reproduced quantitatively** | VXO matches the same 7/8 major events. Episode precision is 68.75% versus 63.2%. |
| Exp6 | **Partially reproduced on covered dates** | The longer VSTOXX history covers six of eight major events: 6/6 for `all_bins`, 5/6 for `spectral_peaks`. |
