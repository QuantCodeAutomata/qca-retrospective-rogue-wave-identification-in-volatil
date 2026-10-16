# Retrospective Rogue-Wave Identification in Volatility Index High Series

Reproduction of the paper's ex-post identification and real-time prediction of rogue-wave-like
volatility extremes in daily high series of VIX, VXO, and VSTOXX.

## Methodology

1. **Envelope extraction** — Mirror series → FFT percentile-based denoising → inverse FFT → Hilbert absolute value  
2. **Peak classification** — Compute peak prominences → SWH = mean of top-third prominences → label peaks >2×SWH and >2.5×SWH  
3. **Schrödinger localization** — Rolling 80-day discrete operator U_k = −|ψ_k|² → minimum eigenpair → width and distance diagnostics  
4. **Real-time warning** — Expanding-sample pipeline → M_i × C_i indicator → threshold trigger

## Repository Structure

```
├── data/           # data_loader.py — loads VIX/VXO/VSTOXX daily highs
├── src/            # Core modules: signal_processing, peak_detection, schrodinger,
│                   #   diagnostics, realtime_pipeline, evaluation, plotting
├── exp/            # Experiment scripts (exp1–exp6)
├── tests/          # pytest test suite (60 tests)
├── results/        # Figures, metrics JSON/CSV, RESULTS.md
└── configs/        # Per-index YAML configs (thresholds, percentiles, etc.)
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Massive API key if available (optional; falls back to Yahoo Finance):
```bash
export MASSIVE_TOKEN=your_key_here
```

## Running Experiments

```bash
python exp/exp1_rogue_wave_identification.py   # Retrospective identification (VIX, VXO, VSTOXX)
python exp/exp2_schrodinger_eigenanalysis.py   # Localization diagnostics (VIX)
python exp/exp3_eigenvalue_gradient.py         # Gradient pre-event signature (VIX)
python exp/exp4_realtime_vix.py                # Real-time warning — VIX (W_i > 300)
python exp/exp5_realtime_vxo.py                # Real-time warning — VXO (W_i > 700)
python exp/exp6_realtime_vstoxx.py             # Real-time warning — VSTOXX (W_i > 300)
```

## Running Tests

```bash
pytest tests/ -q
```

## Key Results (see `results/RESULTS.md` for full details)

| Experiment | Finding |
|------------|---------|
| Exp1       | VIX: 13 major rogue-wave peaks, SWH = 6.48; envelope 63× fewer peaks than raw |
| Exp2       | Width shrinks 0.147→0.017, distance 41.6→4.8 days as peaks approach (Anderson localization) |
| Exp3       | Max \|∇λ_min\| = 317; eigenvalue gradient cleaner than envelope² gradient |
| Exp4 (VIX) | Detects 2008/2020 crises; misses 2018 spike; 69.2% peak detection |
| Exp5 (VXO) | 57.1% OOS detection at 87.5% OOS precision (synthetic data) |
| Exp6 (VSTOXX) | 90.0% detection; methodology transfers across markets |

## Ambiguity Resolution

All unspecified implementation details are documented in `results/RESULTS.md` and inline code
comments. Key choices: symmetric mirroring, Dirichlet boundaries, 92.5% percentile for
descriptive analyses, 95% for real-time, `numpy.gradient` for gradient computation.
