"""Late official KRX observation: missing values never become zero."""
import csv,hashlib,io,json,pathlib,unittest,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ThemeNovember10(unittest.TestCase):
 def test_raw_and_theme_sums(self):
  folder=ROOT/'data/korea-krx-evidence-20261110'
  m=json.loads((folder/'source-manifest.json').read_text())
  k=json.loads((ROOT/'data/korea-market.json').read_text());theme=k['themes']['daily']['2026-11-10']
  self.assertEqual((m['start'],m['end'],m['unit'],m['market']),('2026-11-10','2026-11-10','KRW','ALL'))
  for who,meta in m['investors'].items():
   raw=(folder/meta['file']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),meta['sha256'])
   rows=list(csv.DictReader(io.StringIO(raw.decode(m['encoding']))));by={r['종목코드']:r for r in rows}
   self.assertEqual(len(rows),len(by));self.assertEqual(len(rows),meta['rowCount'])
   self.assertGreater(datetime.datetime.fromisoformat(meta['observedAt']),datetime.datetime.fromisoformat('2026-11-10T19:30:00+09:00'))
   for r in rows:
    for unit in ('거래량','거래대금'):
     vals={key:int(r[unit+'_'+key].replace(',','')) for key in ('매수','매도','순매수')};self.assertEqual(vals['매수']-vals['매도'],vals['순매수'])
   complete=0
   for row in theme['rows']:
    cell=row['coverage'][who];known=[];missing=[]
    for member in cell['memberFlows']:
     expected=int(by[member['code']]['거래대금_순매수'].replace(',','')) if member['code'] in by else None
     self.assertEqual(member['netBuyKRW'],expected)
     (known if expected is not None else missing).append(expected if expected is not None else member['code'])
    self.assertEqual(cell['missingMembers'],missing);self.assertEqual(cell['knownSubtotalKRW'],sum(known));self.assertEqual(cell['netBuyKRW'],None if missing else sum(known));complete+=not missing
   self.assertEqual(complete,{'foreign':9,'institution':3}[who])
  self.assertEqual(theme['sourceStatus'],'official_krx_observed_before_scheduled_final_time')
