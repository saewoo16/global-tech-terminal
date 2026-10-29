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
