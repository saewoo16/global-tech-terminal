import json
from pathlib import Path
import unittest
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]

class FedWatchSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'data/fedwatch.json').read_text())
    def test_aggregated_probabilities_and_sources(self):
        d=self.data
        self.assertEqual(d['view'],'Aggregated')
        self.assertTrue(d['sourceUrl'].startswith('https://www.cmegroup.com/'))
        datetime.fromisoformat(d['observedAt'].replace('Z','+00:00'))
        self.assertEqual(len(d['columnsBps']),4)
        for m in d['meetings']:
            self.assertEqual(len(m['probabilities']),len(d['columnsBps']))
            self.assertAlmostEqual(sum(m['probabilities']),100,places=1)
            self.assertTrue(all(0<=p<=100 for p in m['probabilities']))
    def test_comparison_same_mode_and_precision(self):
        d=self.data;c=d['nextMeetingComparison']
        self.assertEqual(c['view'],'Current')
        self.assertEqual(c['meetingDate'],d['meetings'][0]['date'])
        target=d['currentTargetBps'][0]
        hike=lambda row:sum(p for b,p in zip(c['columnsBps'],row) if b[0]>target)
        for key in ['day','week','month']:
            self.assertAlmostEqual(hike(c['now']['probabilities'])-hike(c[key]['probabilities']),c['hikeChangePp'][key])
        self.assertFalse(d['refresh']['automatedApiVerified'])
    def test_additional_conditional_data_not_aggregated(self):
        c=self.data['conditionalComparisons']
        self.assertIn('not Aggregated',c['methodology'])
        for m in c['comparisons']:
            for key in ['now','day','week','month']:
                self.assertEqual(len(m[key]),len(m['columnsBps']))
                self.assertLess(abs(sum(m[key])-100),.21)
                self.assertTrue(all(0<=p<=100 for p in m[key]))
    def test_macro_collector_wired_without_fake_fedwatch_refresh(self):
        s=(ROOT/'.github/workflows/update.yml').read_text()
        self.assertIn('python scripts/update_macro_quotes.py',s)
        self.assertNotIn('update_fedwatch.py',s)

if __name__=='__main__':unittest.main()
