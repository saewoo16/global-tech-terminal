import json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class October30CallSupplement(unittest.TestCase):
 def setUp(self):self.data=json.loads((ROOT/'data/us_analysis.json').read_text())
 def test_original_release_dates_and_latest_membership(self):
  dates={e['date']:e for e in self.data['entries']}
  latest={r['ticker'] for r in dates['2026-10-30']['earnings']['rows']}
  for ticker in ['IR','VLTO','WY','ERIE','LNT']:
   self.assertNotIn(ticker,latest)
   row=next(r for r in dates['2026-10-29']['earnings']['rows'] if r['ticker']==ticker)
   self.assertEqual(row['releaseDate'],'2026-10-29')
 def test_selected_passages_not_full_verification(self):
  for e in self.data['entries']:
   for row in e.get('earnings',{}).get('rows',[]):
    ids=row.get('callSourceIds',[])
    if row.get('callEvidence',{}).get('type') == 'third_party_transcript_selected_passages':
     self.assertFalse(row['callEvidence']['fullTranscriptVerified'])
     self.assertEqual(row['callPresentationPhase'],'supplement')
     self.assertTrue(row['callEvidence']['limitations'])
     self.assertTrue(row['displayCallHighlights'])
 def test_prerecorded_erie_has_no_invented_qa(self):
  e=next(e for e in self.data['entries'] if e['date']=='2026-10-29')
  row=next(r for r in e['earnings']['rows'] if r['ticker']=='ERIE')
  self.assertFalse(row['callEvidence']['qaVerified'])
  self.assertIn('미실시',row['callStatus'])
if __name__=='__main__':unittest.main()
