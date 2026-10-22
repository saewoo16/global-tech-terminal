import copy,json,re,unittest
from datetime import date
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def assert_period_provenance(test, payload):
 """Rolling panels may advance, but their actual dated sources must advance too."""
 sources={s['id']:s for s in payload['sources']}
 for period, source_period in [('aggregate5d','week'),('monthly','month')]:
  sections=[payload['rankings'][period][inv] for inv in ('foreign','institution')]
  sections.append(payload['themes'][period])
  for section in sections:
   window=section['coverage']
   start,end=window['start'],window['end']
   test.assertEqual(date.fromisoformat(start).isoformat(),start)
   test.assertEqual(date.fromisoformat(end).isoformat(),end)
   test.assertLessEqual(start,end)
   test.assertLessEqual(end,payload['asOf'])
   refs=section['sourceIds']
   test.assertTrue(refs)
   for sid in refs:
    test.assertIn(sid,sources)
    match=re.fullmatch(r'naver-(kospi|kosdaq)-(foreign|institution)-'+source_period+r'-(\d{8})',sid)
    test.assertIsNotNone(match, sid)
    test.assertEqual(match.group(3),end.replace('-',''))
    test.assertIn('periodType='+source_period.upper(),sources[sid]['url'])
   for row in section.get('rows',[]):
    if 'sourceId' in row:
     test.assertIn(row['sourceId'],refs)
    for inv in ('foreign','institution'):
     for component in row.get('coverage',{}).get(inv,{}).get('memberFlows',[]):
      if component.get('netBuyKRW') is not None:
       test.assertIn(component['sourceId'],refs)
   for rows in section.get('byMarket',{}).values():
    for row in rows:
     test.assertIn(row['sourceId'],refs)
def assert_live_session_consistency(test, payload):
    """Check live session relationships, never a fixed calendar-day fixture."""
    as_of = payload['asOf']
    test.assertEqual(date.fromisoformat(as_of).isoformat(), as_of)
    heatmap = payload['heatmaps']
    test.assertEqual(heatmap['asOf'], as_of)
    test.assertLess(heatmap['previousSession'], as_of)
    test.assertTrue(heatmap['regularSessionOnly'])
    for name in ('foreignFlows', 'openInterest'):
        item = payload['futures'][name]
        # A provider may publish later than the cash close. Its actual final
        # row, not today's collection date, must define its displayed date.
        latest = max(row['date'] for row in item['rows'])
        test.assertEqual(item['asOf'], latest)
        test.assertEqual(item['coverage']['end'], latest)
        test.assertLessEqual(latest, as_of)


class KoreanOctober22(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads((R / 'data/korea-market.json').read_text())
        briefings = json.loads((R / 'data/briefings.json').read_text())
        cls.archive = next(e for e in briefings['entries']
                           if e['market'] == 'KR' and e['date'] == '2026-10-22')
        cls.close = json.loads((R / 'data/korea-close-evidence-20261022.json').read_text())
        cls.prices = json.loads((R / 'data/korea-price-evidence-20261022.json').read_text())

    def test_archived_complete_session(self):
        self.assertTrue(self.close['session']['completed'])
        self.assertEqual({r['date'] for r in self.close['session']['latest'].values()}, {'2026-10-22'})
        self.assertEqual(self.archive['reportCutoffAt'], '2026-10-22T18:00:00+09:00')
        self.assertEqual(self.archive['reportCutoffAt'], self.close['reportCutoffAt'])
        self.assertEqual(self.archive['earnings']['rows'], [])
        self.assertEqual({x['name']: x['close'] for x in self.archive['indices']},
                         {'KOSPI': 5533.77, 'KOSDAQ': 764.1})

    def test_archived_cash_flow_matches_collected_evidence(self):
        # Historical regression reads immutable dated observations, not the
        # last row of a live series that will legitimately advance tomorrow.
        collected = {row['market']: row for row in self.close['flows']}
        for brief in self.archive['flows']['rows']:
            actual = collected[brief['market']]
            for key in ('foreign', 'institution', 'individual', 'otherForeign', 'otherCorporation'):
                self.assertEqual(actual[key], brief[key])
            retained = [row for row in self.p['flows']['markets'][brief['market']]['rows']
                        if row['date'] == self.archive['date']]
            for row in retained:
                self.assertTrue(row['snapshotPolicy'])
                for key in ('foreign', 'institution', 'individual', 'otherForeign', 'otherCorporation'):
                    self.assertEqual(row[key], actual[key])

    def test_period_money_is_not_relabelled_today(self):
        assert_period_provenance(self, self.p)

    def test_period_relabel_without_new_sources_rejected(self):
        for kind in ('rankings', 'themes'):
            payload = copy.deepcopy(self.p)
            section = payload[kind]['aggregate5d']
            if kind == 'rankings':
                section = section['foreign']
            section['coverage']['end'] = '2099-01-01'
            payload['asOf'] = '2099-01-01'
            with self.assertRaises(AssertionError):
                assert_period_provenance(self, payload)

    def test_period_source_mismatch_rejected(self):
        payload = copy.deepcopy(self.p)
        payload['rankings']['monthly']['foreign']['sourceIds'] = payload['rankings']['aggregate5d']['foreign']['sourceIds']
        with self.assertRaises(AssertionError):
            assert_period_provenance(self, payload)

    def test_archived_price_sessions(self):
        self.assertEqual(self.prices['window']['target'], '2026-10-22')
        self.assertEqual(self.prices['window']['previous'], '2026-10-21')
        for quote in self.prices['quotes']:
            self.assertEqual(quote['date'], '2026-10-22')
            self.assertEqual(quote['previousDate'], '2026-10-21')
            self.assertAlmostEqual(quote['changePct'],
                                   (quote['regularClose'] / quote['previousRegularClose'] - 1) * 100)

    def test_live_session_consistency(self):
        assert_live_session_consistency(self, self.p)


class LiveSessionRollover(unittest.TestCase):
    def fixture(self):
        # Deliberately synthetic structural fixture, not published market data.
        return {'asOf': '2026-10-23',
                'heatmaps': {'asOf': '2026-10-23', 'previousSession': '2026-10-22', 'regularSessionOnly': True},
                'futures': {name: {'asOf': '2026-10-23', 'coverage': {'end': '2026-10-23'},
                                   'rows': [{'date': '2026-10-23'}]}
                            for name in ('foreignFlows', 'openInterest')}}

    def test_next_session_is_accepted(self):
        assert_live_session_consistency(self, self.fixture())

    def test_stale_heatmap_and_nonregular_session_are_rejected(self):
        for field, value in [('asOf', '2026-10-22'), ('regularSessionOnly', False),
                             ('previousSession', '2026-10-23')]:
            payload = self.fixture()
            payload['heatmaps'][field] = value
            with self.assertRaises(AssertionError):
                assert_live_session_consistency(self, payload)

    def test_futures_redate_without_new_row_is_rejected(self):
        payload = self.fixture()
        payload['futures']['foreignFlows']['rows'][0]['date'] = '2026-10-22'
        with self.assertRaises(AssertionError):
            assert_live_session_consistency(self, payload)

    def test_future_source_date_is_rejected(self):
        payload = self.fixture()
        item = payload['futures']['openInterest']
        item['asOf'] = item['coverage']['end'] = item['rows'][0]['date'] = '2026-10-24'
        with self.assertRaises(AssertionError):
            assert_live_session_consistency(self, payload)


if __name__ == '__main__':
    unittest.main()
