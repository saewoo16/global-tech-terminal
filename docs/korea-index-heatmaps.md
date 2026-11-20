# Domestic index heatmaps

The domestic close tab draws one-day KOSPI 200 and KOSDAQ 150 heatmaps in place.
It uses the site's existing published regular-close snapshot. It neither embeds
Hankyung nor imports or publishes that provider's prices or chart.

The archived fallback matches the 2026-11-12 public market map against security
codes from the repository's dated index ranking evidence. The archived roster
was last corroborated 2026-10-16. The fallback intentionally preserves the true
quote date, 201/201 and 149/150 coverage, and the date of the shares used for
area. It never applies the archived codes to a later quote snapshot.

For future releases verify the two effective-session membership sets against
dated evidence. In `data/korea-market.json` add `heatmaps.indexRosters` with
optional independent `KOSPI` and `KOSDAQ` entries containing `session` (the
snapshot's effective trading date), `asOf` (actual roster verification date),
`codes` (unique six-character securities codes) and `sourceIds` (public snapshot
source IDs). Do not infer membership from market cap or nominal counts. The map
accepts the existing quote section only when it records an actual previous
session, regular-session-only closes, and exclusion of NXT quotes; per-row
dates, closes and return arithmetic must agree. If quotes or roster are
missing, preserve the last normal dated snapshot and do not invent rows.
Verify public reuse permission before introducing any new price data.
