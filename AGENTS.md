# Repository working instructions

This repository implements a documented interpretation of Hayward et al., arXiv:2606.31475v4. It is not a numerically certified replica of author code.

## Invariants

- Real input is actual daily HIGH observations, one row per observed session. No synthetic fallback for missing index data.
- Keep raw inputs, actual bounds, config, software versions and hashes with results.
- Realtime warning at date i uses only values through i. `event_date` is explanatory and must never become an execution date.
- Hilbert is applied before cropping the mirrored extension.
- Descriptive experiments 1–3 use 92.5%; realtime 4–6 and their reference labels use 95%.
- Spectral mode and boundary condition are explicit assumptions, never silently changed to fit published performance.
- Default operator fixes the observed endpoints (L−2 interior); full-L ghost-boundary alternative is explicit.
- Counts distinguish alarm episodes from unique events; late/low signals are not useful major detections.
- Trading-day distances use the supplied observation index, not weekday/calendar approximations.
- Failures remain failures; do not zero-fill or swallow numerical/data errors.
- Preserve original audit archives separately. Public evidence extracts belong in docs/evidence; new runs belong in ignored results directories. Do not commit private equity data or credentials.
- Do not claim synthetic tests or a published-ledger denominator check reproduce performance on real data.

## Validation and entry points

`python -m pytest tests -q`

`python run_experiments.py --index VIX --csv data/VIX.csv --output results/new_run`

`python run_experiments.py --demo --output results/artificial_smoke`

See README.md, docs/ARTICLE_COVERAGE.md and docs/SUPPLEMENT_PROTOCOL.md for conventions and unresolved paper ambiguities. Use separate output directories for alternate settings. Preserve evidence, and state any remaining verification limits accurately.

Write comments and change descriptions in plain English. Explain the numerical rule or measured behavior. Avoid promotional claims and do not call a detection-count match a full replication.
