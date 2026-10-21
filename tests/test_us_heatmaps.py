import copy,importlib.util,json,unittest,sys,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('us_heatmap_validator',ROOT/'scripts/validate_us_heatmaps.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
sys.path.insert(0,str(ROOT/'scripts'))
from build_us_heatmaps import build
class HeatmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/us_heatmaps.json').read_text())
    def test_valid(self):
        self.assertEqual(v.validate(self.data)['verifiedRows'],1006)
        for e in self.data['entries']:
            if e['status']=='verified':
                self.assertEqual(e['coverage']['securities'],503)
                self.assertEqual(e['coverage']['companies'],500)
                self.assertTrue({'GOOG','GOOGL','FOX','FOXA','NWS','NWSA'}.issubset({r['ticker'] for r in e['rows']}))
    def test_rejects_corruption(self):
        cases=[('close',0),('close',float('nan')),('previousClose',-1),('changePct',999),('asOf','2026-10-16'),('previousSession','2026-10-15'),('weight',2),('marketCapUSD',10),('ticker','FAKE')]
        for key,value in cases:
            with self.subTest(key=key,value=value):
                d=copy.deepcopy(self.data);d['entries'][1]['rows'][0][key]=value
                with self.assertRaises((AssertionError,KeyError)):v.validate(d)
    def test_rejects_duplicate_missing_and_fake_day(self):
        for mode in ['duplicate','missing','fake_day']:
            d=copy.deepcopy(self.data)
            if mode=='duplicate':d['entries'][1]['rows'][1]=d['entries'][1]['rows'][0]
            elif mode=='missing':d['entries'][1]['rows'].pop()
            else:d['entries'][0]['rows']=d['entries'][1]['rows']
            with self.assertRaises(AssertionError):v.validate(d)
    def test_future_date_missing_evidence_and_archive_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            for f in (ROOT/'data').glob('us-close-evidence-*.json'):shutil.copy(f,root/'data'/f.name)
            analysis=json.loads((ROOT/'data/us_analysis.json').read_text())
            analysis['entries'].append({'date':'2026-10-21','sessionVerification':{'previousSession':'2026-10-20'}})
            (root/'data/us_analysis.json').write_text(json.dumps(analysis))
            d=build(root,existing=self.data)
            self.assertEqual(d['defaultDate'],'2026-10-20')
            self.assertEqual(d['entries'][-1]['status'],'unavailable')
            self.assertFalse(d['entries'][-1]['rows'])
            self.assertEqual(d['entries'][1:3],self.data['entries'][1:3])
            v.validate(d,root)
    def test_future_verified_date_uses_evidence_coverage(self):
        # Synthetic fixture exercises date expansion, not published market data.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            for f in (ROOT/'data').glob('us-close-evidence-*.json'):shutil.copy(f,root/'data'/f.name)
            e=json.loads((root/'data/us-close-evidence-20261020.json').read_text())
            e['session']='2026-10-21'
            e['sessionVerification'].update(exchangeDate='2026-10-21',previousSession='2026-10-20',closedAt='2026-10-21T16:00:00-04:00')
            c=e['screens']['coverage'];c.update(asOf='2026-10-21',previousSession='2026-10-20',universeAsOf='2026-10-21',retrievedAt='2026-10-21T22:00:00Z',selected=1,securities=1,companies=1,dailyValid=1)
            e['screens']['dailyRows']=e['screens']['dailyRows'][:1]
            e['screens']['dailyRows'][0].update(asOf='2026-10-21',previousSession='2026-10-20')
            (root/'data/us-close-evidence-20261021.json').write_text(json.dumps(e))
            (root/'data/us_analysis.json').write_text(json.dumps({'entries':[{'date':'2026-10-21'}]}))
            d=build(root,existing=self.data)
            self.assertEqual(d['defaultDate'],'2026-10-21')
            self.assertEqual(d['entries'][-1]['coverage']['verified'],1)
            self.assertEqual(d['entries'][1:3],self.data['entries'][1:3])
            v.validate(d,root)
if __name__=='__main__':unittest.main()
