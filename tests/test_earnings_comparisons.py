import unittest
from scripts.earnings_comparisons import compare, normalize_metric
class ComparisonTests(unittest.TestCase):
 def test_positive(self):
  self.assertEqual(compare(120,100)[0],'+20.00%'); self.assertAlmostEqual(compare(120,100)[1],20)
 def test_turnaround(self):
  self.assertEqual(compare(1,-1),('흑자 전환',None))
  self.assertEqual(compare(-1,1),('적자 전환',None))
  self.assertEqual(compare(-1,-2),('적자 축소',None))
  self.assertEqual(compare(-2,-1),('적자 확대',None))
 def test_zero(self):
  self.assertEqual(compare(1,0),('흑자 전환',None))
  self.assertEqual(compare(0,0),('변동 없음',None))
 def test_margin(self):
  text,v=compare(12,10,margin=True);self.assertEqual(text,'+2.00pp');self.assertEqual(v,2)
 def test_missing(self):
  self.assertEqual(compare(None,3),('미확인',None))
 def test_normalize(self):
  m={'label':'EPS','raw':{'value':.8,'yearAgoQuarter':.52,'previousQuarter':.7}}
  normalize_metric(m);self.assertEqual(m['yoy'],'+53.85%');self.assertEqual(m['qoq'],'+14.29%')
