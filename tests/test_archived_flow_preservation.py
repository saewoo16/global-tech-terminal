"""Archive-derived cash-flow protection, including the actual Nov 5/6 revision."""
import copy
from contextlib import ExitStack
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

UNSET = object()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_korean_market as update


class ReplayClock(datetime):
    observed_at = '2026-11-06T11:30:00+00:00'

    @classmethod
    def now(cls, tz=None):
        return datetime.fromisoformat(cls.observed_at).astimezone(tz or timezone.utc)


def small_fixture(day='2026-11-09'):
    """Explicitly synthetic next-session archive with section-level sources only."""
    sources, markets, archived = [], {}, []
    for market in update.FLOW_MARKETS:
        sid = 'synthetic-' + market
        url = ('https://stock.naver.com/api/domestic/market/trend/daily?'
               f'tradeType=KRX&marketType={market}&bizdate={day.replace("-", "")}&startIdx=0&pageSize=30')
        sources.append({'id': sid, 'title': 'Synthetic fixture', 'url': url})
        values = dict(zip(update.FLOW_FIELDS, [1, 2, -3, None, 0]))
        row = {'date': day, **values, 'source': url, 'note': 'Keep this original observation',
               'observedAt': day+'T08:31:00+00:00', 'customEvidence': {'items': ['original']}}
        markets[market] = {'rows': [row], 'coverage': {'start': day, 'end': day, 'count': 1,
            'requestedStart': '2023-01-01'}, 'sourceIds': [sid], 'status': 'partial',
            'note': 'Original section note', 'observedAt': day+'T08:31:00+00:00'}
        archived.append({'market': market, **values, 'observedAt': row['observedAt']})
    payload = {'sources': copy.deepcopy(sources), 'flows': {'unit': '억원', 'markets': markets}}
    archive = {'schemaVersion': 1, 'entries': [{'market': 'KR', 'date': day, 'status': 'partial',
        'title': 'Synthetic next-session fixture', 'sources': sources,
        'flows': {'unit': '억원', 'sourceIds': [source['id'] for source in sources], 'rows': archived}}]}
    return payload, archive


def incoming_row(section, day=None):
    row = copy.deepcopy(section['rows'][-1])
    row['date'] = day or row['date']
    row['otherForeign'] = 10
    row['foreign'] = 123
    row['retrievedAt'] = row['date']+'T11:30:00+00:00'
    row.pop('snapshotPolicy', None)
    return row


class ArchivedFlowPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.published = json.loads((ROOT/'data/korea-market.json').read_text())
        cls.archive = json.loads((ROOT/'data/briefings.json').read_text())
        raw = json.loads((ROOT/'data/korea-turnover-history-evidence-20261106.json').read_text())
        cls.snapshots = {}
        for snapshot in raw['snapshots']:
            query = parse_qs(urlsplit(snapshot['url']).query)
            if query['tradeType'] == ['KRX'] and query['startIdx'][0] in ('0', '1'):
                cls.snapshots[snapshot['url']] = snapshot

    def setUp(self):
        self.payload, self.briefings = small_fixture()
        ReplayClock.observed_at = '2026-11-06T11:30:00+00:00'

    def replay_fetch(self, url):
        snapshot = self.snapshots[url]
        ReplayClock.observed_at = snapshot['observedAt']
        return json.dumps(snapshot['data'])

    def collect_replay(self, market):
        with patch.object(update, 'fetch', side_effect=self.replay_fetch), patch.object(update, 'datetime', ReplayClock):
            return update.collect_flows(market, '2026-11-06')

    def assert_rejected_without_mutation(self, payload=UNSET, archive=UNSET):
        payload = self.payload if payload is UNSET else payload
        archive = self.briefings if archive is UNSET else archive
        before = copy.deepcopy((payload, archive))
        with self.assertRaises((ValueError, KeyError, TypeError)):
            update.archived_flow_dates(payload, archive)
        self.assertEqual((payload, archive), before)

    def test_all_published_archive_dates_and_all_recorded_categories_agree(self):
        protected = update.archived_flow_dates(self.published, self.archive)
        coordinates = 0
        for entry in self.archive['entries']:
            if entry['market'] != 'KR':
                continue
            self.assertEqual(entry['flows']['unit'], self.published['flows']['unit'])
            for archived in entry['flows']['rows']:
                coordinates += 1
                market, day = archived['market'], entry['date']
                matches = [row for row in self.published['flows']['markets'][market]['rows'] if row['date'] == day]
                self.assertEqual(len(matches), 1, (market, day))
                self.assertIn(day, protected[market])
                for field in update.FLOW_FIELDS:
                    if field in archived:
                        self.assertEqual(matches[0][field], archived[field], (market, day, field))
        self.assertEqual(coordinates, sum(map(len, protected.values())))
        self.assertGreaterEqual(coordinates, 32)

    def test_real_nov5_nov6_raw_replay_preserves_every_archived_whole_row(self):
        protected = update.archived_flow_dates(self.published, self.archive)
        archive_before = copy.deepcopy(self.archive)
        for market in update.FLOW_MARKETS:
            original = self.published['flows']['markets'][market]
            old = {row['date']: row for row in original['rows']}
            raw_rows = self.collect_replay(market)
            raw_by_date = {row['date']: row for row in raw_rows}
            for day in ('2026-11-05', '2026-11-06'):
                self.assertNotIn('snapshotPolicy', old[day])
                for field in update.FLOW_FIELDS[:3]:
                    self.assertNotEqual(old[day][field], raw_by_date[day][field])
            if market == 'KOSPI':
                self.assertEqual(old['2026-11-06']['foreign'], -27360)
                self.assertEqual(raw_by_date['2026-11-06']['foreign'], -26897.08)
            candidate, diagnostics = update.merge_flow_observations(original, raw_rows, '2023-11-04', protected[market])
            after = {row['date']: row for row in candidate['rows']}
            for day in protected[market]:
                self.assertEqual(after[day], old[day], (market, day))
            self.assertEqual({key: value for key, value in original.items() if key not in ('rows', 'coverage', 'status')},
                             {key: value for key, value in candidate.items() if key not in ('rows', 'coverage', 'status')})
            conflicts = {item['date']: item for item in diagnostics['notApplied']}
            for day in ('2026-11-05', '2026-11-06'):
                self.assertEqual(conflicts[day]['action'], 'not_applied')
                self.assertEqual(conflicts[day]['retrievedAt'], raw_by_date[day]['retrievedAt'])
                self.assertEqual(conflicts[day]['source'], raw_by_date[day]['source'])
                self.assertEqual(conflicts[day]['incomingValues']['foreign'], raw_by_date[day]['foreign'])
                self.assertEqual(conflicts[day]['preservedValues']['foreign'], old[day]['foreign'])
                self.assertNotIn(day, diagnostics['appliedObservationDates'])
                self.assertNotIn('providerFinalizedAt', conflicts[day])
            second, repeated = update.merge_flow_observations(candidate, raw_rows, '2023-11-04', protected[market])
            self.assertEqual(second, candidate)
            self.assertEqual(repeated['notApplied'], diagnostics['notApplied'])
        self.assertEqual(self.archive, archive_before)

    def test_future_partial_archive_without_flags_protects_all_metadata_and_null(self):
        protected = update.archived_flow_dates(self.payload, self.briefings)
        before = copy.deepcopy(self.payload)
        original = self.payload['flows']['markets']['KOSPI']
        candidate, diagnostics = update.merge_flow_observations(original, [incoming_row(original)], '2023-01-01', protected['KOSPI'])
        self.assertEqual(candidate, original)
        self.assertIsNone(candidate['rows'][0]['otherForeign'])
        self.assertEqual(candidate['rows'][0]['otherCorporation'], 0)
        self.assertEqual(diagnostics['appliedObservationDates'], [])
        self.assertEqual(diagnostics['notAppliedCount'], 1)
        self.assertEqual(self.payload, before)
        later, _ = update.merge_flow_observations(candidate, [incoming_row(original, '2026-11-10')], '2023-01-01', protected['KOSPI'])
        self.assertEqual(later['status'], 'partial')
        self.assertIsNone(later['rows'][0]['otherForeign'])
        self.assertEqual(later['rows'][0], original['rows'][0])

    def test_each_of_five_recorded_fields_null_zero_and_missing_are_checked(self):
        for field in update.FLOW_FIELDS:
            for mutation in ('change', 'missing'):
                payload = copy.deepcopy(self.payload)
                row = payload['flows']['markets']['KOSPI']['rows'][0]
                if mutation == 'missing':
                    row.pop(field)
                else:
                    row[field] = 0 if row[field] is None else row[field] + 1
                with self.subTest(field=field, mutation=mutation):
                    self.assert_rejected_without_mutation(payload, self.briefings)
        self.payload['flows']['markets']['KOSPI']['rows'][0]['foreign'] = True
        self.assert_rejected_without_mutation()

    def test_optional_unrecorded_categories_are_not_fabricated_in_archive(self):
        for row in self.briefings['entries'][0]['flows']['rows']:
            row.pop('otherForeign')
            row.pop('otherCorporation')
        before = copy.deepcopy(self.briefings)
        self.assertEqual(update.archived_flow_dates(self.payload, self.briefings)['KOSPI'], {'2026-11-09'})
        self.assertEqual(self.briefings, before)

    def test_wrong_units_at_every_level_fail_closed(self):
        for location in ('flows', 'market', 'stored', 'archive', 'archived'):
            payload, archive = copy.deepcopy((self.payload, self.briefings))
            target = {'flows': payload['flows'], 'market': payload['flows']['markets']['KOSPI'],
                'stored': payload['flows']['markets']['KOSPI']['rows'][0],
                'archive': archive['entries'][0]['flows'], 'archived': archive['entries'][0]['flows']['rows'][0]}[location]
            target['unit'] = 'KRW'
            with self.subTest(location=location):
                self.assert_rejected_without_mutation(payload, archive)

    def test_duplicate_archive_entry_market_and_stored_date_fail_closed(self):
        for mutation in ('entry', 'market', 'stored', 'source'):
            payload, archive = copy.deepcopy((self.payload, self.briefings))
            if mutation == 'entry':
                archive['entries'].append(copy.deepcopy(archive['entries'][0]))
            elif mutation == 'market':
                archive['entries'][0]['flows']['rows'].append(copy.deepcopy(archive['entries'][0]['flows']['rows'][0]))
            elif mutation == 'stored':
                payload['flows']['markets']['KOSPI']['rows'].append(copy.deepcopy(payload['flows']['markets']['KOSPI']['rows'][0]))
            else:
                payload['sources'].append(copy.deepcopy(payload['sources'][0]))
            with self.subTest(mutation=mutation):
                self.assert_rejected_without_mutation(payload, archive)

    def test_missing_stored_row_and_missing_archive_fail_closed(self):
        for archive in (None, {}, {'schemaVersion': 1, 'entries': []}):
            self.assert_rejected_without_mutation(self.payload, archive)
        self.payload['flows']['markets']['KOSPI']['rows'] = []
        self.assert_rejected_without_mutation()

    def test_unknown_empty_and_malformed_archive_sources_fail_closed(self):
        for refs in ([], ['unknown'], ['synthetic-KOSPI', 'synthetic-KOSPI'], 'synthetic-KOSPI', [None]):
            archive = copy.deepcopy(self.briefings)
            archive['entries'][0]['flows']['sourceIds'] = refs
            self.assert_rejected_without_mutation(self.payload, archive)

    def test_empty_sourced_archive_rows_and_wrong_archive_scope_fail_closed(self):
        for mutation in ('empty', 'wrong_scope', 'invalid_query', 'invalid_timestamp'):
            archive = copy.deepcopy(self.briefings)
            entry = archive['entries'][0]
            if mutation == 'empty':
                entry['flows']['rows'] = []
            elif mutation == 'wrong_scope':
                entry['sources'][0]['url'] = entry['sources'][0]['url'].replace('tradeType=KRX', 'tradeType=NXT')
            elif mutation == 'invalid_query':
                entry['sources'][0]['url'] = entry['sources'][0]['url'].replace('bizdate=20261109', 'bizdate=invalid')
            else:
                entry['sources'][0]['retrievedAt'] = 'invalid'
            with self.subTest(mutation=mutation):
                self.assert_rejected_without_mutation(self.payload, archive)

    def test_archive_missing_an_entire_market_cannot_unfreeze_that_market(self):
        for market in update.FLOW_MARKETS:
            archive = copy.deepcopy(self.briefings)
            archive['entries'][0]['flows']['rows'] = [row for row in archive['entries'][0]['flows']['rows'] if row['market'] != market]
            with self.subTest(market=market):
                self.assert_rejected_without_mutation(self.payload, archive)

    def test_future_unsourced_empty_partial_entry_does_not_require_invented_flows(self):
        future = copy.deepcopy(self.briefings['entries'][0])
        future['date'] = '2026-11-10'
        future['flows'].update(rows=[], sourceIds=[])
        self.briefings['entries'].append(future)
        protected = update.archived_flow_dates(self.payload, self.briefings)
        self.assertEqual(protected, {market: {'2026-11-09'} for market in update.FLOW_MARKETS})

    def test_optional_future_partial_flows_absent_or_empty_keep_existing_protection(self):
        for kind in ('absent', 'empty_object'):
            archive = copy.deepcopy(self.briefings)
            future = copy.deepcopy(archive['entries'][0])
            future['date'] = '2026-11-10'
            if kind == 'absent':
                future.pop('flows')
            else:
                future['flows'] = {}
            archive['entries'].append(future)
            with self.subTest(kind=kind):
                before = copy.deepcopy(archive)
                self.assertEqual(update.archived_flow_dates(self.payload, archive),
                                 {market: {'2026-11-09'} for market in update.FLOW_MARKETS})
                self.assertEqual(archive, before)

    def test_claimed_flows_without_valid_rows_still_fail_closed(self):
        for section in ({'unit': '억원', 'sourceIds': ['synthetic-KOSPI']},
                        {'unit': '억원', 'foreign': 1},
                        {'unit': '억원', 'sourceIds': [], 'rows': None},
                        {'unit': '억원', 'sourceIds': ['synthetic-KOSPI'], 'rows': []}):
            archive = copy.deepcopy(self.briefings)
            future = copy.deepcopy(archive['entries'][0])
            future.update(date='2026-11-10', flows=section)
            archive['entries'].append(future)
            with self.subTest(section=section):
                self.assert_rejected_without_mutation(self.payload, archive)

    def test_matching_observed_at_allows_distinct_later_retrieval_events(self):
        current = self.payload['flows']['markets']['KOSPI']['rows'][0]
        archived = self.briefings['entries'][0]['flows']['rows'][0]
        current['retrievedAt'] = '2026-11-09T11:30:00+00:00'
        update.archived_flow_dates(self.payload, self.briefings)
        archived['retrievedAt'] = '2026-11-09T10:30:00+00:00'
        before = copy.deepcopy((self.payload, self.briefings))
        update.archived_flow_dates(self.payload, self.briefings)
        self.assertEqual((self.payload, self.briefings), before)
        # Matching retrieval does not excuse mismatched explicit observation.
        archived['retrievedAt'] = current['retrievedAt']
        current['observedAt'] = '2026-11-09T08:32:00+00:00'
        self.assert_rejected_without_mutation()

    def test_explicit_observation_does_not_hide_malformed_retrieval_time(self):
        for side in ('stored', 'archive', 'source'):
            payload, archive = copy.deepcopy((self.payload, self.briefings))
            owner = {'stored': payload['flows']['markets']['KOSPI']['rows'][0],
                     'archive': archive['entries'][0]['flows']['rows'][0],
                     'source': archive['entries'][0]['sources'][0]}[side]
            owner['retrievedAt'] = '2026-11-09T11:30:00'
            with self.subTest(side=side):
                self.assert_rejected_without_mutation(payload, archive)

    def test_stored_retrieval_only_fallback_still_rejects_observation_mismatch(self):
        current = self.payload['flows']['markets']['KOSPI']['rows'][0]
        current['retrievedAt'] = current.pop('observedAt')
        update.archived_flow_dates(self.payload, self.briefings)
        current['retrievedAt'] = '2026-11-09T11:30:00+00:00'
        self.assert_rejected_without_mutation()

    def test_observation_timestamp_aliases_still_detect_mismatch(self):
        row = self.briefings['entries'][0]['flows']['rows'][0]
        row['retrievedAt'] = row.pop('observedAt')
        update.archived_flow_dates(self.payload, self.briefings)
        row['retrievedAt'] = '2026-11-09T11:30:00+00:00'
        self.assert_rejected_without_mutation()

    def test_explicit_row_source_ids_are_supported_and_mismatches_rejected(self):
        for market, archived in zip(update.FLOW_MARKETS, self.briefings['entries'][0]['flows']['rows']):
            archived['sourceIds'] = ['synthetic-'+market]
            self.payload['flows']['markets'][market]['rows'][0]['sourceId'] = 'synthetic-'+market
        self.briefings['entries'][0]['flows'].pop('sourceIds')
        update.archived_flow_dates(self.payload, self.briefings)
        self.payload['flows']['markets']['KOSPI']['rows'][0]['sourceId'] = 'synthetic-KOSDAQ'
        self.assert_rejected_without_mutation()

    def test_source_market_provider_scope_and_timestamps_cannot_change(self):
        for mutation in ('market', 'tradeType', 'provider', 'observedAt', 'naiveTime'):
            payload = copy.deepcopy(self.payload)
            row = payload['flows']['markets']['KOSPI']['rows'][0]
            if mutation == 'market':
                row['source'] = row['source'].replace('marketType=KOSPI', 'marketType=KOSDAQ')
            elif mutation == 'tradeType':
                row['source'] = row['source'].replace('tradeType=KRX', 'tradeType=NXT')
            elif mutation == 'provider':
                row['source'] = row['source'].replace('stock.naver.com', 'example.com')
            else:
                row['observedAt'] = '2026-11-09T11:00:00' + ('' if mutation == 'naiveTime' else '+00:00')
            with self.subTest(mutation=mutation):
                self.assert_rejected_without_mutation(payload, self.briefings)

    def test_legacy_query_window_is_not_observation_date_or_timestamp(self):
        row = self.payload['flows']['markets']['KOSPI']['rows'][0]
        row['source'] = row['source'].replace('bizdate=20261109&startIdx=0', 'bizdate=20261113&startIdx=1')
        row.pop('observedAt')
        before = copy.deepcopy(row)
        update.archived_flow_dates(self.payload, self.briefings)
        self.assertEqual(row, before)

    def test_cutoff_retains_archive_and_explicit_flags_but_prunes_ordinary_history(self):
        original = self.payload['flows']['markets']['KOSPI']
        old = copy.deepcopy(original['rows'][0])
        old.update(date='2020-01-02', snapshotPolicy='Keep independent snapshot')
        original['rows'].insert(0, old)
        original['rows'].insert(1, {**copy.deepcopy(old), 'date': '2020-01-03', 'snapshotPolicy': ''})
        new = incoming_row(original, '2026-11-10')
        candidate, _ = update.merge_flow_observations(original, [new], '2026-11-10', {'2026-11-09'})
        self.assertEqual([row['date'] for row in candidate['rows']], ['2020-01-02', '2026-11-09', '2026-11-10'])
        self.assertEqual(candidate['rows'][0], old)
        self.assertEqual(candidate['coverage']['start'], '2020-01-02')
        self.assertEqual(candidate['coverage']['end'], '2026-11-10')
        self.assertEqual(candidate['coverage']['count'], 3)

    def test_new_unarchived_session_and_revisions_still_apply(self):
        original = self.payload['flows']['markets']['KOSPI']
        first = incoming_row(original, '2026-11-10')
        candidate, summary = update.merge_flow_observations(original, [first], '2023-01-01', {'2026-11-09'})
        self.assertEqual(candidate['rows'][-1], first)
        self.assertEqual(summary['appliedObservationDates'], ['2026-11-10'])
        revised = {**first, 'foreign': 456}
        candidate, _ = update.merge_flow_observations(candidate, [revised], '2023-01-01', {'2026-11-09'})
        self.assertEqual(candidate['rows'][-1], revised)

    def test_empty_duplicate_and_late_invalid_incoming_never_partially_mutate(self):
        original = self.payload['flows']['markets']['KOSPI']
        good = incoming_row(original, '2026-11-10')
        bad = incoming_row(original, '2026-11-11')
        bad['otherCorporation'] = None
        for rows in ([], [good, good], [good, bad]):
            before = copy.deepcopy(original)
            with self.assertRaises(ValueError):
                update.merge_flow_observations(original, rows, '2023-01-01', {'2026-11-09'})
            self.assertEqual(original, before)

    def test_generic_merge_rejects_missing_coverage_without_partial_rows(self):
        original = {'rows': [{'date': '2026-11-09', 'value': 1}]}
        before = copy.deepcopy(original)
        with self.assertRaises(KeyError):
            update.merge_series(original, [{'date': '2026-11-10', 'value': 2}], '2023-01-01')
        self.assertEqual(original, before)

    def test_conflict_diagnostics_are_bounded_and_latest_only(self):
        original = self.payload['flows']['markets']['KOSPI']
        base = copy.deepcopy(original['rows'][0])
        original['rows'] = [{**copy.deepcopy(base), 'date': f'2026-10-{day:02d}'} for day in range(1, 32)]
        rows = [{**copy.deepcopy(row), 'foreign': 999, 'otherForeign': 0,
                 'retrievedAt': '2026-11-09T11:30:00+00:00'} for row in original['rows']]
        candidate, summary = update.merge_flow_observations(original, rows, '2023-01-01', {row['date'] for row in original['rows']})
        self.assertEqual(candidate['rows'], original['rows'])
        self.assertEqual(summary['notAppliedCount'], 31)
        self.assertEqual(len(summary['notApplied']), update.MAX_FLOW_CONFLICTS)
        self.assertEqual(summary['omittedOlderConflicts'], 11)
        self.assertEqual(summary['notApplied'][-1]['date'], '2026-10-31')

    def test_raw_collector_rejects_duplicate_investor_and_future_observations(self):
        first = next(snapshot for url, snapshot in self.snapshots.items() if 'marketType=KOSPI' in url and 'startIdx=0' in url)
        for mutation in ('duplicate_investor', 'future'):
            raw = copy.deepcopy(first['data'])
            if mutation == 'duplicate_investor':
                raw['content'][0]['netAmounts'].append(copy.deepcopy(raw['content'][0]['netAmounts'][0]))
            else:
                raw['content'][0]['bizdate'] = '20261109'
            with self.subTest(mutation=mutation), patch.object(update, 'fetch', return_value=json.dumps(raw)):
                with self.assertRaises(ValueError):
                    update.collect_flows('KOSPI', '2026-11-06')

    def test_raw_collector_rejects_duplicate_dates_across_pages(self):
        first = next(snapshot for url, snapshot in self.snapshots.items() if 'marketType=KOSPI' in url and 'startIdx=0' in url)
        with patch.object(update, 'fetch', return_value=json.dumps(first['data'])):
            with self.assertRaisesRegex(ValueError, 'duplicate daily flow'):
                update.collect_flows('KOSPI', '2026-11-06')

    def main_mocks(self, stack, market_file, archive_file):
        stack.enter_context(patch.object(update, 'FILE', market_file))
        stack.enter_context(patch.object(update, 'ARCHIVE', archive_file))
        stack.enter_context(patch.object(update, 'datetime', ReplayClock))
        stack.enter_context(patch.object(update, 'fetch', side_effect=self.replay_fetch))
        stack.enter_context(patch.dict('os.environ', {'SKIP_KR_LIQUIDITY': '1'}))
        for name in ('collect_foreign_flows', 'collect_open_interest', 'update_rankings', 'collect_themes'):
            stack.enter_context(patch.object(update, name, side_effect=RuntimeError('Explicit offline collector fixture')))
        stack.enter_context(patch('sys.stdout', new=io.StringIO()))
        stack.enter_context(patch('sys.stderr', new=io.StringIO()))
        return stack.enter_context(patch.object(update, 'atomic_write'))

    def test_main_actual_raw_replay_preserves_archive_and_other_panels(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            market_file, archive_file = Path(directory)/'market.json', Path(directory)/'briefings.json'
            market_file.write_text(json.dumps(self.published))
            archive_file.write_text(json.dumps(self.archive))
            write = self.main_mocks(stack, market_file, archive_file)
            update.main()
            write.assert_called_once()
            candidate = write.call_args.args[0]
            protected = update.archived_flow_dates(candidate, self.archive)
            self.assertEqual(update.validate(candidate), [])
            for market in update.FLOW_MARKETS:
                before = {row['date']: row for row in self.published['flows']['markets'][market]['rows']}
                after = {row['date']: row for row in candidate['flows']['markets'][market]['rows']}
                for day in protected[market]:
                    self.assertEqual(after[day], before[day])
                summary = candidate['refresh']['cashFlowObservations'][market]
                self.assertIn('2026-11-05', summary['preservedDates'])
                self.assertIn('2026-11-06', summary['preservedDates'])
                self.assertNotIn('2026-11-06', summary['appliedObservationDates'])
            for key in self.published.keys() - {'flows', 'refresh', 'asOf', 'updatedAt', 'requestedWindow'}:
                self.assertEqual(candidate[key], self.published[key], key)
            self.assertEqual(json.loads(archive_file.read_text()), self.archive)
            self.assertEqual(json.loads(market_file.read_text()), self.published)

    def test_main_missing_malformed_or_mismatched_archive_blocks_collection_and_write(self):
        with tempfile.TemporaryDirectory() as directory:
            market_file, archive_file = Path(directory)/'market.json', Path(directory)/'briefings.json'
            market_file.write_text(json.dumps(self.published))
            bad = copy.deepcopy(self.archive)
            next(entry for entry in bad['entries'] if entry['market'] == 'KR')['flows']['rows'][0]['foreign'] += 1
            for content in (None, '{invalid json', json.dumps(bad)):
                if content is None:
                    archive_file.unlink(missing_ok=True)
                else:
                    archive_file.write_text(content)
                with self.subTest(content=None if content is None else content[:20]), ExitStack() as stack:
                    write = self.main_mocks(stack, market_file, archive_file)
                    collect = stack.enter_context(patch.object(update, 'collect_flows'))
                    with self.assertRaises((OSError, ValueError)):
                        update.main()
                    collect.assert_not_called()
                    write.assert_not_called()

    def test_main_one_market_fetch_failure_keeps_whole_section_and_other_market_progresses(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            market_file, archive_file = Path(directory)/'market.json', Path(directory)/'briefings.json'
            market_file.write_text(json.dumps(self.published))
            archive_file.write_text(json.dumps(self.archive))
            write = self.main_mocks(stack, market_file, archive_file)
            def fetch(url):
                if 'marketType=KOSPI' in url and 'startIdx=1' in url:
                    raise TimeoutError('Synthetic KOSPI second-page outage')
                return self.replay_fetch(url)
            stack.enter_context(patch.object(update, 'fetch', side_effect=fetch))
            update.main()
            candidate = write.call_args.args[0]
            self.assertEqual(candidate['flows']['markets']['KOSPI'], self.published['flows']['markets']['KOSPI'])
            self.assertNotIn('flows.KOSPI', candidate['refresh']['refreshedSections'])
            self.assertIn('flows.KOSDAQ', candidate['refresh']['refreshedSections'])
            self.assertTrue(any(item['section'] == 'flows.KOSPI' and 'TimeoutError' in item['message'] for item in candidate['refresh']['failures']))
            update.archived_flow_dates(candidate, self.archive)

    def test_main_preserved_only_rows_are_not_reported_as_newly_refreshed(self):
        payload = copy.deepcopy(self.published)
        for market in update.FLOW_MARKETS:
            payload['flows']['markets'][market]['rows'] = [copy.deepcopy(next(row for row in payload['flows']['markets'][market]['rows'] if row['date'] == '2026-11-06'))]
            payload['flows']['markets'][market]['coverage'].update(start='2026-11-06', end='2026-11-06', count=1)
        archive = copy.deepcopy(self.archive)
        archive['entries'] = [entry for entry in archive['entries'] if entry['market'] == 'KR' and entry['date'] == '2026-11-06']
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            market_file, archive_file = Path(directory)/'market.json', Path(directory)/'briefings.json'
            market_file.write_text(json.dumps(payload))
            archive_file.write_text(json.dumps(archive))
            write = self.main_mocks(stack, market_file, archive_file)
            raw = {market: self.collect_replay(market)[-1:] for market in update.FLOW_MARKETS}
            stack.enter_context(patch.object(update, 'collect_flows', side_effect=lambda market, today: raw[market]))
            update.main()
            candidate = write.call_args.args[0]
            self.assertEqual(candidate['flows'], payload['flows'])
            self.assertFalse(any(section.startswith('flows.') for section in candidate['refresh']['refreshedSections']))
            for summary in candidate['refresh']['cashFlowObservations'].values():
                self.assertEqual(summary['appliedObservationDates'], [])
                self.assertEqual(summary['notAppliedCount'], 1)


if __name__ == '__main__':
    unittest.main()
