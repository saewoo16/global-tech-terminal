#!/usr/bin/env bash
# Run against the candidate files, before any commit or public publication.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python -m unittest discover -s tests -v
for test in tests/test_*.cjs; do
  node "$test"
done
python scripts/validate_us_analysis.py
python scripts/validate_us_heatmaps.py
python scripts/validate_korean_market.py
# No --entry: validate the preserved archive without rewriting it.
python scripts/manage_briefings.py
