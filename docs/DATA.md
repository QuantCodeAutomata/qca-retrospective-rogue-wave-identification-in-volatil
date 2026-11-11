# Data and provenance

The algorithm requires actual daily High in index points. Close-only history is not a substitute. The public evidence contains derived warning and event ledgers, effective configurations, hashes and validation receipts. Raw vendor exports, normalized daily price inputs and full offline replay bundles are kept separately. A reader needs the corresponding input snapshot for an exact numerical replay; the public evidence alone cannot reconstruct it.

The 11 November chart refresh uses CBOE VIX through 10 November 2026, the final CBOE VXO quotation on 23 September 2021, and a comdirect/Eurex VSTOXX series covering May 2005 through 10 November 2026. [Source checks](judge_20261111/evidence.json) · [Input reconstruction](judge_20261111/REPLAY.md).

## Sources in the frozen comparisons

| Input | Source | Frozen use |
|---|---|---|
| VIX | [CBOE VIX History CSV](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv) | Historical comparison through 31 December 2025; later case study through 9 November 2026 |
| VXO | [CBOE archive XLS](https://cdn.cboe.com/resources/us/indices/vxoarchive.xls) and [current CSV](https://cdn.cboe.com/resources/us/indices/vxocurrent.csv) | 2 January 1986–31 December 2020 |
| VSTOXX DAG export | Supplied historical OHLC export; source identity not independently certified | 3 September 2010–22 November 2024, 3,626 rows |
| VSTOXX Investing export | Historical OHLC export retained in the offline bundle | 28 December 2012–28 March 2025, 3,117 rows |
| VSTOXX Portara sample | Short supplied sample | 90 observations; insufficient for performance estimation |
| STOXX Close comparison | [STOXX historical V2TX file](https://www.stoxx.com/document/Indices/Current/HistoricalData/h_v2tx.txt) | Calendar sensitivity only; never an input replacement for High |

These are the recorded source URLs, not a promise that the endpoints or their contents will remain unchanged. No paid data purchase was made for these runs. The public repository does not distribute server equity data, credentials or private infrastructure settings.

## Hashes

Each [run manifest](evidence/run_index.json) records the original CSV hash, normalized input CSV hash, date range, row count, series digest and effective settings. The original source CSV can contain more history than the selected run. Its hash must not be confused with the normalized input saved after applying bounds.

| Raw file / retrieval | SHA-256 |
|---|---|
| VIX CSV, 22 October 2026 | `9355bb6a65841239c1b17877d981812adcdf725acabac3be8655eb1f23e1cf1f` |
| VIX CSV, 10 November 2026 | `0fbd2010663102746b54b12bf96ab0ca4add0c922aebc4dabb0a84cd9c8b0e63` |
| VXO archive XLS, 22 October 2026 | `3b3e40080ba89197603774ab454c57aacc557825ea929e41b366d87a4751038d` |
| VXO current CSV, 22 October 2026 | `4aa84cf9b4c287163a95ca0d0bdfad5ce7aa14430c92f52014958d1873d864b9` |

The judge-review follow-up rebuilt the VIX/VXO normalized inputs and all six VSTOXX input variants from the retained source exports. The [rebuild receipt](evidence/source_rebuild.json) reports exact hash agreement.

## Data limits

The 10 November VIX download has 9,312 observations. Its 9,299 overlapping High values agree with the earlier download within 1e−10. The raw OHLC has 47 inconsistent rows in older history; none is in 2025–2026. High values were not silently repaired.

VSTOXX exports have source and calendar limitations. The comparison Close series lacks records on six dates present in the Investing export. A sensitivity run removes those six dates, but their absence from a different file does not establish that no index session occurred. The same comparison has six observations missing from the Investing export in March 2025. We neither fill missing High values nor replace them with Close.

Full author-period VSTOXX High, the authors' snapshots and their precise VIX/VSTOXX final observation dates remain unavailable. Paper catalog dates are retained exactly and linked to their source and hashes in [the catalog manifest](../verification/source_evidence/paper_catalog_manifest.json).
