import datetime as dt
import json
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

class October28Analysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT/'data/us_analysis.json').read_text())
        cls.entry = next(e for e in cls.payload['entries'] if e['date']=='2026-10-28')
        cls.evidence = json.loads((ROOT/'data/us-close-evidence-20261028.json').read_text())

    def test_latest_completed_session_and_actual_cutoff(self):
        e=self.entry
        self.assertGreaterEqual(max(x['date'] for x in self.payload['entries']), e['date'])
        self.assertEqual(e['sessionStatus'], 'closed')
        self.assertEqual(e['sessionVerification']['previousSession'],'2026-10-27')
        cutoff=dt.datetime.fromisoformat(e['reportCutoffAt'])
        self.assertEqual(cutoff.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),'2026-10-29T07:00:00+09:00')
        self.assertGreaterEqual(dt.datetime.fromisoformat(self.payload['updatedAt']),cutoff)

    def test_breadth_from_real_daily_prices(self):
        rows=self.evidence['screens']['dailyRows']
        counts={'advancing':0,'declining':0,'unchanged':0}
        for r in rows:
            counts['advancing' if r['close']>r['previousClose'] else 'declining' if r['close']<r['previousClose'] else 'unchanged']+=1
            self.assertAlmostEqual(r['changePct'],(r['close']/r['previousClose']-1)*100,places=7)
        self.assertEqual(self.entry['breadth']['counts'],counts)
        self.assertEqual(self.entry['breadth']['validCount'],len(rows))

    def test_earnings_et_attribution_and_basis(self):
        rows=self.entry['earnings']['rows']
        self.assertEqual(len(rows),len({r['ticker'] for r in rows}))
        for r in rows:
            self.assertEqual(r['releaseDate'],'2026-10-28')
            self.assertEqual(r['presentationVersion'],3)
            self.assertEqual([m['label'] for m in r['metrics']],['매출','매출총이익','매출총이익률','영업이익','EPS'])
            self.assertEqual(len(r['quarterlyHistory']['rows']),4)
            stamp=r.get('releaseTiming',{}).get('publishedAt')
            if stamp:
                self.assertEqual(dt.datetime.fromisoformat(stamp).astimezone(ZoneInfo('America/New_York')).date().isoformat(),'2026-10-28')

    def test_previous_sessions_preserved(self):
        dates={e['date'] for e in self.payload['entries']}
        self.assertTrue({'2026-10-20','2026-10-23','2026-10-26','2026-10-27'}<=dates)
        self.assertNotIn('marketCapUnusualMovers',self.entry)

if __name__=='__main__':
    unittest.main()
