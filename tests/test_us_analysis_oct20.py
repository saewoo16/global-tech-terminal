import copy,datetime as dt,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from validate_us_analysis import validate_unusual_movers
class October20Verification(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.e=next(e for e in json.loads((ROOT/'data/us_analysis.json').read_text())['entries'] if e['date']=='2026-10-20')
 def test_distinct_universes(self):
  self.assertEqual(len(self.e['constituents']),503)
  c=self.e['marketCapUnusualMovers'];self.assertEqual(c['coverage']['selected'],500);self.assertEqual(c['coverage']['universeAsOf'],'2026-10-19')
  self.assertEqual({r['ticker'] for r in c['rows']},{'MMM','GM'})
  self.assertEqual(len(self.e['unusualMovers']['rows']),6)
 def test_cap500_evidence_reproduces_filter(self):
  x=json.loads((ROOT/'data/us-cap500-evidence-20261020.json').read_text());self.assertEqual(len(x['rows']),500)
  eligible=[]
  for r in x['rows']:
   a,b=r['bars']['2026-10-19'],r['bars']['2026-10-20'];pct=(b['close']/a['close']-1)*100;ratio=b['volume']/a['volume']
   self.assertAlmostEqual(r['changePct'],pct);self.assertAlmostEqual(r['volumeRatio'],ratio)
   if abs(pct)>=5 and ratio>=2:eligible.append(r['ticker'])
  self.assertEqual(set(eligible),{'MMM','GM'})
 def test_reject_duplicate_rank(self):
  c=copy.deepcopy(self.e['marketCapUnusualMovers']);c['constituents'][1]['rank']=1
  with self.assertRaises(AssertionError):validate_unusual_movers(c,set(),dt.date(2026,10,20),cap500=True)
 def test_reject_wrong_volume(self):
  c=copy.deepcopy(self.e['marketCapUnusualMovers']);c['rows'][0]['volumeRatio']=2
  with self.assertRaises(AssertionError):validate_unusual_movers(c,set(),dt.date(2026,10,20),cap500=True)
 def test_seventeen_reports_four_metrics_and_reported_quarters(self):
  rows=self.e['earnings']['rows'];self.assertEqual(len(rows),17)
  for r in rows:
   self.assertEqual(r['presentationVersion'],2);self.assertEqual(len(r['metrics']),4)
   quarters=r['quarterlyHistory']['rows'];self.assertEqual(len(quarters),4)
   for q in quarters:
    if q.get('revenue') and q.get('operatingIncome') is not None:self.assertAlmostEqual(q['operatingMargin'],q['operatingIncome']/q['revenue']*100)
  after=[r for r in rows if r['priceReaction']['afterHours']['status']=='verified'];self.assertEqual(len(after),5)
  for r in after:
   a=r['priceReaction']['afterHours'];self.assertGreater(dt.datetime.fromisoformat(a['observedAt']),dt.datetime.fromisoformat(r['releaseTiming']['publishedAt']))
   self.assertAlmostEqual(a['changePct'],(a['price']/r['priceReaction']['regular']['close']-1)*100)
 def test_all_panels_have_correct_dates(self):
  self.assertEqual(self.e['coverage']['asOf'],'2026-10-20');self.assertEqual(self.e['coverage']['dailyValid'],503)
  for r in self.e['sectors']['rows']:self.assertEqual(r['calculation']['asOf'],'2026-10-20')
  for r in self.e['indices']:self.assertEqual(r['previousDate'],'2026-10-19')
if __name__=='__main__':unittest.main()
