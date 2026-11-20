# Explorer: independent official close refresh

The fast path reads the two official, openly licensed Taiwan cash market closing CSVs in parallel. It produces only the small Taiwan official-close snapshot that the existing Explorer already reads, without fetching or altering adjusted chart history, market caps, FX, or quarterly filings. No new service, branch, credential, scheduler, or network access setting is required.

After the intended Taiwan regular session has closed, check the dates and the full configured venue roster without changing any file:

```sh
python scripts/prepare_explorer_taiwan_closes.py --session YYYY-MM-DD
```

If a fresh session is available and the existing publication policy permits the update, prepare only the canonical local file:

```sh
python scripts/prepare_explorer_taiwan_closes.py --session YYYY-MM-DD --apply
```

Review the changed file and run the existing required validation before publishing. The script never commits, pushes, or deploys. Use the existing daily Explorer schedule rather than creating another scheduler. On holidays or delayed source releases it will stop on a session mismatch, with no changes. An unchanged recheck is a successful no-op; changed same-day closes are held for manual revision review. A mixed session, missing listing, partial file, or wrong date stops the entire candidate and leaves the earlier verified file in place. Archived source files can be replayed in read-only mode using `--twse-csv` and `--tpex-csv`.

Sources: [TWSE dataset](https://data.gov.tw/en/datasets/11549), [TPEx dataset](https://data.gov.tw/dataset/11371), [Taiwan Open Government Data License v1](https://data.gov.tw/license). Add venues only after confirming date, regular-session definition, attribution, and public-display rights. Leave other exchanges and the full-history refresh independent.
