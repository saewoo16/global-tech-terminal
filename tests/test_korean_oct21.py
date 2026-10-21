"""October 21 closing snapshot provenance and precision regression checks."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class KoreanOct21Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT/'data/korea-market.json').read_text())
        cls.entry = next(e for e in json.loads((ROOT/'data/briefings.json').read_text())['entries'] if e['market']=='KR' and e['date']=='2026-10-21')

    def test_close_and_flow_precision(self):
        self.assertEqual([(r['close'],r['changePct'])for r in self.entry['indices']], [(5735.66,3.29),(792.76,1.38)])
        expected = {'KOSPI':(6434.84,-745.72,-11089.25),'KOSDAQ':(-1747.28,1052.2,554.24)}
        for row in self.entry['flows']['rows']:
            self.assertEqual(tuple(row[k]for k in ('foreign','institution','individual')),expected[row['market']])
            history=next(r for r in self.data['flows']['markets'][row['market']]['rows']if r['date']=='2026-10-21')
            for key in ('foreign','institution','individual','otherForeign','otherCorporation'):
                self.assertEqual(row[key],history[key])
            self.assertTrue(history['snapshotPolicy'])
            self.assertTrue(history['retrievedAt'].startswith('2026-10-21'))

    def test_real_money_ranking_and_independent_periods(self):
        day=self.data['rankings']['daily']['2026-10-21']
        for key in ('foreign','institution'):
            self.assertEqual(day[key]['coverage']['end'],'2026-10-21')
            for market,rows in day[key]['byMarket'].items():
                self.assertEqual(len(rows),15)
                self.assertEqual(len({r['code']for r in rows}),15)
                self.assertTrue(all(r['value']>0 for r in rows))
        self.assertEqual(day['foreign']['byMarket']['KOSPI'][0]['value'],4721.6)

    def test_new_release_universe_and_metrics(self):
        rows=self.entry['earnings']['rows']
        self.assertEqual({r['ticker']for r in rows},{'207940','010120','060370'})
        for row in rows:
            self.assertIn('2026-10-21',row['period'])
            self.assertEqual([m['label']for m in row['metrics']],['매출액','영업이익','영업이익률','당기순이익'])
            self.assertEqual(len(row['quarterlyHistory']['rows']),4)
