# Descriptive article diagnostics: Figure 5 and S1-S4

These outputs reproduce specified calculations and document an interpretation where the manuscript is incomplete. They are **descriptive**, not an independent forecasting test or a numerical certification of the authors' output. They do not tune the causal indicator. The source warning ledger is copied, never changed or deduplicated. The saved run manifest fixes the source sample and its first observation.

## Figure 5: lagged Pearson correlation

For each integer lag from -30 through +30, compute `corr(M_i, High[i+lag])` on the actual observed-session calendar. Positive lag denotes future High. Keep only valid pairs with `M_i > 0.0001`. Shift before filtering M_i; missing calendar dates are not inserted. Use signal/receipt dates, never explanatory event dates. Store the pair count and correlation at every lag. Fewer than two pairs or constant input produces an undefined correlation and explicit status, not zero. The manuscript names the variables, cutoff and Pearson statistic; the exact alignment formula here is our declared convention. One index is written per invocation; unavailable VSTOXX cannot be replaced by another series.

## S1: raw-wave aftershocks and envelope decay

The fixed anchors are 2008-10-13 (300 following observations), 2020-03-16 (150), and 2011-08-09 (300). These are **our frozen horizons**: the plotted tick labels do not fully specify the authors' fitting intervals. The anchor must occur in the supplied calendar and its complete horizon must be available; otherwise report unavailable without moving the date or shortening the fit.

Compute raw local peaks and prominences over the entire frozen High sample. SWH is the mean of the largest `ceil(n_peaks/3)` raw prominences. An aftershock is a raw local peak whose prominence strictly exceeds that SWH. Count each selected peak once; exclude the anchor itself; include points `t=0..H`, with `N(0)=0`. This is a deliberate interpretation of the ambiguous S1 caption, consistent with the paper's prominence-based definition of wave height. It is not an assertion that the authors counted the same events. In particular, raw High is not compared to a prominence threshold. All raw peaks, selected flags and cumulative counts are exported.

Fit the integral of `K/(t+c)^p`:

```
N_fit(t) = K * ((t+c)^(1-p) - c^(1-p)) / (1-p), p != 1
N_fit(t) = K * log(1+t/c),                         p == 1
```

Use unweighted least squares at every integer t=1..H. Constrain K>=0, 0<=p<=3 and 0.1<=c<=H. Profile K analytically as `max(0, dot(F,N)/dot(F,F))`, optimizing `(p, log(c))`. Run all nine starts `p={0.25,1,2}`, `c={1,10,H/3}`. Use bounded least squares with ftol=xtol=gtol=1e-10 and max_nfev=10000. Select minimum SSE among converged starts; SSE differences within `1e-10*max(1,min_SSE)` are ties resolved by smaller p, then smaller c. Evaluate the integral using log1p/expm1; within `abs(p-1)<1e-8`, use its logarithmic limit.

Fewer than three events gives `insufficient_events` (zero gives `no_events`). No converged start gives `optimizer_failed`, including messages from failed starts. Parameters at a constraint boundary are retained with `boundary_solution`; the boundary tolerance is 1e-6 (c's upper boundary also uses relative tolerance 1e-6; K=0 uses 1e-10). R-squared is `1-SSE/SST` on t=1..H and undefined if SST=0. These bounds, optimizer choices and failure policies are ours. No interval, parameter bound or event definition is selected to match the paper's R-squared. Cumulative-count R-squared is descriptive, not evidence from independent observations.

S1b uses the descriptive envelope (92.5% by default and the explicitly selected FFT mode), the 2008 anchor plus its next 300 observations, and a **global 1-based index from the first observation of the frozen input sample**. Fit `ln(envelope)=intercept+slope*ln(global_index)` by OLS with intercept over the entire fixed interval. Export input dates/indices, logarithms, fitted values and coefficients. Nonpositive/nonfinite envelope values fail this panel explicitly, without deleting rows. The exact author index origin and interval are unknown.

The integrated Omori model is motivated by [Lillo and Mantegna (2003)](https://journals.aps.org/pre/abstract/10.1103/PhysRevE.68.016119), whose financial application concerns threshold exceedances of absolute returns. That source does not establish the event definition adopted for VIX in this reconstruction.

## S2: envelope increments

On the full descriptive envelope compute `env[t+k]-env[t]` for k=1,2,5,10,20 observed sessions. No filling or interpolation. For each k, standardize by that lag's full-sample mean and population standard deviation (`ddof=0`). Zero variance makes standardized differences undefined, while raw differences are preserved. Insufficient history is explicit.

The raw panel uses 100 equal-width bins spanning the pooled raw increments of all available lags. The standardized panel independently uses 100 shared bins spanning its pooled finite standardized increments. Constant pooled values use NumPy's usual half-unit range expansion. Export all 101 edges, bin counts, density=count/(n*bin_width), and every increment. Plot zero-density bins as gaps on a logarithmic density axis. The shared bins and ddof convention are explicit implementation choices; they are not reported as author-specified settings.

## S3 and S4: receipt versus explanatory event dates

S3 selects VIX receipt dates in calendar years 2018 and 2020; display High, C_i on receipt dates, and M_i both on receipt dates and explanatory event dates. S4 selects VXO receipt dates in 2020 and displays High, W_i and the configured warning threshold, plus M_i on both dates. Preserve **every received row**, including repeated event dates. Points overlap visually when dates coincide; no averaging, maximum, deduplication or reclassification is applied. Export the complete selected ledgers. Event dates must be observed dates no later than receipt dates and never become execution timestamps.

Absent warnings or absent year slices produce unavailable statuses. Each available slice reports its actual first/last receipt dates and counts; it does not imply complete market-year coverage. S1/S2 are applicable only to VIX, S3 only to VIX, S4 only to VXO. Other indices receive `not_applicable`, while Figure 5 is available for any supplied index with a valid warning ledger.

## Output contract

`run_paper_diagnostics(index_name, highs, warnings, config, output_dir, descriptive_envelope=None)` writes `paper_<index>_*` CSV/PNG files plus `paper_<index>_diagnostics_summary.json` and returns the same summary dictionary. Every figure's status, relative artifact names and explicit limitations are retained. Missing data are reported without substitution. Invalid supplied inputs raise; they are not ordinary zero signals. This module does not fetch data or access private server caches.
