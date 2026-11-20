# Close-only domestic index heatmaps

> Historical input contract only. The public domestic close tab now links to the Hankyung whole-market originals, which provide their own 1D/1W/1M controls. Do not collect or publish this retired input for the main view; do not copy or embed Hankyung data or claim the original page is close-only.

The public #korea tab displays separate KOSPI 200 and KOSDAQ 150 treemaps.
The rendering input is optional `indexHeatmaps` in `data/korea-market.json`;
the legacy whole-market and sampled maps are separate historical references.
If no validated index input matches the briefing's trading date, the section
shows that official closes are unconfirmed and links out to the provider's own
index views. The external pages are not dashboard data or guaranteed close-only.

For a candidate snapshot, use `asOf`, `membershipAsOf` (same local trade date),
`previousAsOf` (preceding actual KRX trading date), `priceBasis:
official_regular_close`, and `sourceIds` referencing the date-specific evidence
in the parent `sources`. In `indices`, supply arrays named `KOSPI200` and
`KOSDAQ150` containing exactly 200 and 150 constituents respectively. Each row
has `code`, `name`, `asOf`, `close`, `previousClose` and `marketCapKRW`. Optional
industry information uses the existing heatmap row format. The page computes
returns from the two closes and sizes cells by closing market cap.

Verify both exact dated constituent rosters, the exchange sessions, official
regular-session closing data, market-cap basis, and permission for public
redistribution before writing any snapshot. The validator checks structure;
it cannot verify availability, rights, session status or honest source labels.
Use the existing Korean market update window; no extra scheduler, intraday
widget, or new vendor permission is required by the display code.
