import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from korean_turnover import validate
class TurnoverTests(unittest.TestCase):
 def fixture(self):
  row={'date':'2026-10-29','turnover':123.45,'sourceValue':'12345','sourceUnit':'백만원','conversionToEokKRW':.01,'observedAt':'2026-10-29T15:00:00+00:00'}
  section={'markets':{m:{'unit':'억원','scope':'whole-market','sourceIds':['src'],'rows':[dict(row)],'coverage':{'start':row['date'],'end':row['date'],'count':1}} for m in ['KOSPI','KOSDAQ']}}
  return section,[{'id':'src'}]
 def test_precision_and_scopes(self):
  s,ids=self.fixture();self.assertEqual(validate(s,ids),[])
  s['markets']['KOSPI']['rows'][0]['turnover']=123;self.assertTrue(validate(s,ids))
 def test_unknown_not_zero(self):
  s,ids=self.fixture();r=s['markets']['KOSPI']['rows'][0];r['turnover']=None;self.assertTrue(validate(s,ids));r['missingReason']='원천 미공표';self.assertEqual(validate(s,ids),[])
 def test_invalid_scope_and_date(self):
  s,ids=self.fixture();s['markets']['KOSPI']['scope']='top20';self.assertTrue(validate(s,ids))
class UpdaterTests(unittest.TestCase):
 def test_unchanged_and_narrow_merge(self):
  import update_korean_turnover as u
  from unittest.mock import patch
  s,ids=TurnoverTests().fixture();payload={'marketTurnover':s,'sources':ids,'otherPanel':{'untouched':True}}
  same=s['markets']['KOSPI']['rows'][0]
  with patch.object(u,'collect',return_value=[dict(same)]):self.assertIs(u.update(payload,'2026-10-29'),payload)
  newer=dict(same,date='2026-10-30')
  with patch.object(u,'collect',return_value=[newer]):
   changed=u.update(payload,'2026-10-30');self.assertEqual(changed['otherPanel'],payload['otherPanel']);self.assertEqual(len(payload['marketTurnover']['markets']['KOSPI']['rows']),1);self.assertEqual(len(changed['marketTurnover']['markets']['KOSPI']['rows']),2)
if __name__=='__main__': unittest.main()

class ComparisonTurnoverTests(unittest.TestCase):
 def fixture(self):
  import copy
  s,ids=TurnoverTests().fixture()
  for market,legacy in s['markets'].items():
   legacy['comparisonSeries']={}
   for key in ('regular','integrated'):
    row=copy.deepcopy(legacy['rows'][0]);row.update(scopeVerified=True,valueStatus='final',sourceIds=['src'])
    legacy['comparisonSeries'][key]={'market':market,'unit':'억원','scope':'whole-market','venues':['KRX'] if key=='regular' else ['KRX','NXT'],'sessionScope':'regular' if key=='regular' else 'all-sessions','label':key,'scopeNote':'verified source coverage','status':'verified','asOf':row['date'],'rows':[row],'sourceIds':['src'],'coverage':{'start':row['date'],'end':row['date'],'count':1}}
  return s,ids
 def test_independent_series_valid(self):
  s,ids=self.fixture();self.assertEqual(validate(s,ids),[])
 def test_no_scope_guess(self):
  s,ids=self.fixture();s['markets']['KOSPI']['comparisonSeries']['regular']['sessionScope']='unverified';self.assertTrue(validate(s,ids))
 def test_integrated_no_double_add_scope(self):
  s,ids=self.fixture();s['markets']['KOSPI']['comparisonSeries']['integrated']['venues']=['KRX','NXT','NXT'];self.assertTrue(validate(s,ids))
 def test_actual_asof_and_precision(self):
  s,ids=self.fixture();s['markets']['KOSPI']['comparisonSeries']['integrated']['asOf']='2026-10-30';self.assertTrue(validate(s,ids))
 def test_unverified_observation_rejected(self):
  s,ids=self.fixture();s['markets']['KOSPI']['comparisonSeries']['regular']['rows'][0]['scopeVerified']=False;self.assertTrue(validate(s,ids))
 def test_unavailable_not_zero(self):
  s,ids=self.fixture();a=s['markets']['KOSPI']['comparisonSeries']['integrated'];a.update(rows=[],coverage={'count':0},asOf=None,status='unavailable');self.assertEqual(validate(s,ids),[])
