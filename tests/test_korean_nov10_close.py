"""Nov10 observed session, exact indices and stored source evidence."""
import hashlib,json,math,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/'data'/name).read_text())
class November10Close(unittest.TestCase):
 def test_official_completed_session(self):
  e=read('korea-session-evidence-20261110.json')
  self.assertEqual(e['date'],'2026-11-10')
  self.assertNotIn(e['date'],e['holidays'])
  self.assertEqual(e['actualCompletedFlowDates'],{'KOSPI':e['date'],'KOSDAQ':e['date']})
  self.assertTrue(e['isCompletedRegularSession'])
  self.assertGreater(e['observedAt'],'2026-11-10T06:30:00+00:00')
 def test_index_and_flow_evidence(self):
  e=next(x for x in read('briefings.json')['entries'] if x['market']=='KR' and x['date']=='2026-11-10')
  self.assertEqual([(r['name'],r['close'],r['previousClose']) for r in e['indices']],[('KOSPI',5239.13,5018.85),('KOSDAQ',667.61,638.97)])
  ids={s['id'] for s in e['sources']}
  for r in e['indices']:self.assertTrue(set(r['sourceIds'])<=ids)
  raw=read('korea-close-evidence-20261110.json')
  for row in e['flows']['rows']:
   observation=raw['flows'][row['market']]['rows'][0]
   for key in ('foreign','institution','individual','otherForeign','otherCorporation'):
    self.assertEqual(row[key],observation[key])
   self.assertEqual(row['observedAt'],observation['retrievedAt'])
 def test_raw_source_hashes(self):
  for s in read('korea-close-evidence-20261110.json')['sources']:
   self.assertEqual(hashlib.sha256((ROOT/s['rawFile']).read_bytes()).hexdigest(),s['storedFileSha256'])
 def test_earnings_releases_and_four_quarter_math(self):
  e=next(x for x in read('briefings.json')['entries'] if x['market']=='KR' and x['date']=='2026-11-10')
  rows=e['earnings']['rows'];ids={s['id'] for s in e['sources']}
  self.assertGreaterEqual(len(rows),11)
  keys=[(r['ticker'],r['releaseDate'],r['period'],r.get('releaseType','results')) for r in rows]
  self.assertEqual(len(keys),len(set(keys)))
  for row in rows:
   self.assertEqual(row['releaseDate'],'2026-11-10')
   self.assertEqual(len(row['quarterlyHistory']['rows']),4)
   for q in row['quarterlyHistory']['rows']:
    self.assertTrue(set(q['sourceIds'])<=ids)
    if q.get('revenue') not in (None,0) and q.get('operatingIncome') is not None:
     self.assertTrue(math.isclose(q['operatingMargin'],q['operatingIncome']/q['revenue']*100,abs_tol=1e-9))
if __name__=='__main__':unittest.main()


class November10DatedMoney(unittest.TestCase):
 def test_period_source_amounts_and_actual_dates(self):
  import sys
  sys.path.insert(0,str(ROOT/'scripts'))
  from korean_rankings_source import preferred
  k=read('korea-period-snapshot-20261109.json')
  for api,key,start in [('WEEK','aggregate5d','20261103'),('MONTH','monthly','20261013')]:
   for m in ('KOSPI','KOSDAQ'):
    for inv,who in [('FOREIGNER','foreign'),('ORGANIZATION','institution')]:
     raw=read('korea-source-evidence-20261110/'+api+'-'+m+'-'+inv+'.json')['data']['sections']['buyRankList']
     expected=[r for r in raw if r['type']=='ST' and not preferred(r)][:15]
     actual=k['rankings'][key][who]['byMarket'][m]
     self.assertEqual([r['code'] for r in actual],[r['itemcode'] for r in expected])
     for a,r in zip(actual,expected):
      self.assertEqual((r['bizdateFrom'],r['bizdateTo']),(start,'20261109'))
      self.assertEqual(a['valueKRW'],int(r['accTradeAmount']))
      self.assertAlmostEqual(a['value']*1e8,a['valueKRW'],delta=.01)
