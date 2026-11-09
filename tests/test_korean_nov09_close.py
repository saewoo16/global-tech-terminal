"""Nov9 observed session, exact indices and stored source evidence."""
import hashlib,json,math,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'data'/name).read_text())
class November09Close(unittest.TestCase):
 def test_official_completed_session(self):
  e=read('korea-session-evidence-20261109.json')
  self.assertEqual(e['date'],'2026-11-09')
  self.assertNotIn(e['date'],e['holidays'])
  self.assertEqual(e['actualCompletedFlowDates'],{'KOSPI':e['date'],'KOSDAQ':e['date']})
  self.assertTrue(e['isCompletedRegularSession'])
  self.assertGreater(e['observedAt'],'2026-11-09T06:30:00+00:00')
 def test_index_and_flow_evidence(self):
  e=next(x for x in read('briefings.json')['entries'] if x['market']=='KR' and x['date']=='2026-11-09')
  self.assertEqual([(r['name'],r['close'],r['previousClose']) for r in e['indices']],[('KOSPI',5018.85,5059.69),('KOSDAQ',638.97,644.27)])
  ids={s['id'] for s in e['sources']}
  for r in e['indices']:self.assertTrue(set(r['sourceIds'])<=ids)
  raw=read('korea-close-evidence-20261109.json')
  for row in e['flows']['rows']:
   observation=raw['flows'][row['market']]['rows'][0]
   for key in ('foreign','institution','individual','otherForeign','otherCorporation'):
    self.assertEqual(row[key],observation[key])
   self.assertEqual(row['observedAt'],observation['retrievedAt'])
 def test_raw_source_hashes(self):
  for s in read('korea-close-evidence-20261109.json')['sources']:
   self.assertEqual(hashlib.sha256((ROOT/s['rawFile']).read_bytes()).hexdigest(),s['storedFileSha256'])
 def test_earnings_releases_and_four_quarter_math(self):
  e=next(x for x in read('briefings.json')['entries'] if x['market']=='KR' and x['date']=='2026-11-09')
  rows=e['earnings']['rows'];ids={s['id'] for s in e['sources']}
  self.assertGreaterEqual(len(rows),14)
  keys=[(r['ticker'],r['releaseDate'],r['period'],r.get('releaseType','results')) for r in rows]
  self.assertEqual(len(keys),len(set(keys)))
  for row in rows:
   self.assertEqual(row['releaseDate'],'2026-11-09')
   self.assertEqual(len(row['quarterlyHistory']['rows']),4)
   for q in row['quarterlyHistory']['rows']:
    self.assertTrue(set(q['sourceIds'])<=ids)
    if q.get('revenue') not in (None,0) and q.get('operatingIncome') is not None:
     self.assertTrue(math.isclose(q['operatingMargin'],q['operatingIncome']/q['revenue']*100,abs_tol=1e-9))
if __name__=='__main__':unittest.main()

class November09OfficialThemes(unittest.TestCase):
 def test_source_files_and_missing_values(self):
  m=read('korea-krx-evidence-20261109/source-manifest.json')
  for investor,s in m['investors'].items():
   self.assertEqual(hashlib.sha256((ROOT/s['file']).read_bytes()).hexdigest(),s['storedFileSha256'])
  k=read('korea-market.json');t=k['themes']['daily']['2026-11-09']
  self.assertEqual(t['status'],'partial')
  self.assertIn('2026-11-06',k['themes']['daily'])
  for investor,count in [('foreign',9),('institution',1)]:
   self.assertEqual(sum(r['coverage'][investor]['status']=='complete' for r in t['rows']),count)
   for row in t['rows']:
    c=row['coverage'][investor]
    vals=[x['netBuyKRW'] for x in c['memberFlows'] if x['netBuyKRW'] is not None]
    self.assertEqual(sum(vals),c['knownSubtotalKRW'])
    if c['missingMembers']:
     self.assertIsNone(c['netBuyKRW']);self.assertIsNone(row[investor])
    else:self.assertEqual(c['netBuyKRW'],sum(vals))
