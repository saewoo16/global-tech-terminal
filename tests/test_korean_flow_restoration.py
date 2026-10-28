"""Regression evidence for the delayed Oct 28 investor-flow release, no live I/O."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = json.loads((ROOT / 'data/korea-flow-restoration-evidence-20261028.json').read_text())
DATA = json.loads((ROOT / 'data/korea-market.json').read_text())
DAY = '2026-10-28'


class KoreanFlowRestorationTests(unittest.TestCase):
    def test_raw_periods_are_actual_money_not_estimated_shares(self):
        responses = EVIDENCE['rawInvestorResponses']
        self.assertEqual(len(responses), 12)
        for key, response in responses.items():
            period = key.rsplit('_', 1)[1]
            start = {'DAY': '20261028', 'WEEK': '20261022', 'MONTH': '20260929'}[period]
            for side, rows in response['data']['sections'].items():
                self.assertGreaterEqual(len(rows), 99)
                for row in rows:
                    self.assertEqual((row['bizdateFrom'], row['bizdateTo']), (start, '20261028'))
                    self.assertIsNot(row.get('estimated'), True)
                    if key.endswith('FOREIGNER_DAY'):
                        self.assertIs(row['estimated'], False)
                    amount = int(row['accTradeAmount'])
                    self.assertGreater(amount if side == 'buyRankList' else -amount, 0)

    def test_theme_cells_match_original_signed_money_and_keep_incomplete_totals_null(self):
        sections = [('DAY', DATA['themes']['daily'].get(DAY)),
                    ('WEEK', DATA['themes']['aggregate5d']), ('MONTH', DATA['themes']['monthly'])]
        for period, section in sections:
            # Later genuine releases are allowed; never pin the live dashboard to this fixture.
            if not section or section.get('coverage', {}).get('end') != DAY:
                continue
            self.assertEqual(len(section['rows']), 13)
            for investor, source_name in [('foreign', 'FOREIGNER'), ('institution', 'ORGANIZATION')]:
                raw = {}
                for market in ['KOSPI', 'KOSDAQ']:
                    response = EVIDENCE['rawInvestorResponses'][f'{market}_{source_name}_{period}']
                    for rows in response['data']['sections'].values():
                        for row in rows:
                            raw[row['itemcode']] = int(row['accTradeAmount'])
                for row in section['rows']:
                    cell = row['coverage'][investor]
                    known = []
                    for member in cell['memberFlows']:
                        expected = raw.get(member['code'])
                        self.assertEqual(member['netBuyKRW'], expected)
                        if expected is not None:
                            known.append(expected)
                    self.assertEqual(cell['availableCount'], len(known))
                    self.assertEqual(cell['knownSubtotalKRW'], sum(known))
                    self.assertAlmostEqual(cell['knownSubtotalEok'], sum(known) / 1e8)
                    if len(known) < cell['expectedCount']:
                        self.assertIsNone(row[investor])
                        self.assertIsNone(cell['netBuyKRW'])

    def test_turnover_is_closed_aftermarket_not_regular_session_certified(self):
        coverage = EVIDENCE['summary']['turnoverCoverage']
        self.assertEqual(coverage['end'], DAY)
        self.assertEqual(coverage['sourceTradeSession'], 'AFTER_MARKET')
        self.assertEqual(coverage['sourceMarketStatus'], 'CLOSE')
        self.assertIs(coverage['regularSessionOnlyVerified'], False)
        for row in EVIDENCE['rawTurnover']['data']:
            self.assertEqual(row['tradingSessionType'], 'AFTER_MARKET')
            self.assertEqual(row['marketStatus'], 'CLOSE')
            self.assertGreater(int(row['tradeAmount']), 0)
        section = DATA['rankings']['daily'].get(DAY, {}).get('tradedValue')
        if section:
            audit = {row['itemcode']: row for row in EVIDENCE['turnoverUniverseAudit']['publishedRows']}
            self.assertEqual(len(section['rows']), 20)
            for rows in [section['rows'], *section['byMarket'].values()]:
                for row in rows:
                    self.assertAlmostEqual(row['value'], int(audit[row['code']]['tradeAmount']) / 1e8)
            self.assertIs(section['coverage']['regularSessionOnlyVerified'], False)

    def test_daily_stock_ranks_keep_distinct_1530_source_snapshot(self):
        day = DATA['rankings']['daily'].get(DAY)
        if day:
            for investor in ['foreign', 'institution']:
                self.assertEqual(day[investor]['coverage']['snapshotAt'], DAY + 'T15:30:00+09:00')
                self.assertEqual(len(day[investor]['rows']), 15)
                self.assertIn('연합뉴스', day[investor]['note'])


if __name__ == '__main__':
    unittest.main()
