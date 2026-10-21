import unittest
from scripts.korean_etf_representatives import build_representatives

class RepresentativeTests(unittest.TestCase):
    def cap(self, code, value, kind='ST'):
        return {'itemcode':code,'itemname':code,'marketSum':str(value),'listedStockCnt':'1000000','nowPrice':str(value // 1000000),'type':kind}
    def row(self, code, count, weight=0, isin=None):
        return {'componentItemCode':code,'componentName':str(code),'componentCount':str(count),'referenceDate':'2026-10-21','componentIsinCode':isin or ('KR7'+code+'003'),'weight':str(weight)}
    def test_market_cap_not_weight(self):
        rows=[self.row('000001',4,90),self.row('000002',4,1),self.row('000003',4,5),self.row('000004',4,4)]
        market={c:self.cap(c,v*1000000) for c,v in [('000001',1),('000002',4),('000003',3),('000004',2)]}
        r=build_representatives('091160',rows,market,'2026-10-21T07:00:00Z')
        self.assertEqual([m['code'] for m in r['members']],['000002','000003','000004'])
    def test_missing_fails_closed(self):
        r=build_representatives('091160',[self.row('000001',1)],{},'now')
        self.assertEqual(r['status'],'partial');self.assertEqual(r['members'],[]);self.assertEqual(len(r['missingComponents']),1)
    def test_incomplete_count_fails_closed(self):
        r=build_representatives('091160',[self.row('000001',2)],{'000001':self.cap('000001',1000000)},'now')
        self.assertEqual(r['status'],'partial')
    def test_foreign_scope_explicit(self):
        rows=[self.row('000001',2),self.row(None,2,isin='JP3914400001')]
        r=build_representatives('0247S0',rows,{'000001':self.cap('000001',1000000)},'now')
        self.assertEqual(r['label'],'ETF 국내 편입종목 시총 상위');self.assertEqual(r['foreignExcludedCount'],1)
    def test_reit_infra_scope(self):
        rows=[self.row('000001',1)]
        r=build_representatives('329200',rows,{'000001':self.cap('000001',1000000,'RT')},'now')
        self.assertEqual(len(r['members']),1);self.assertIn('RT',r['includedInstrumentTypes'])
    def test_decimal_cap_precision(self):
        cap=self.cap('000001',1000000);cap['marketSum']='1000000.0'
        r=build_representatives('091160',[self.row('000001',1)],{'000001':cap},'now')
        self.assertEqual(r['members'][0]['marketCapKRW'],1000000)
    def test_mixed_dates_fail_closed(self):
        rows=[self.row('000001',2),self.row('000002',2)];rows[1]['referenceDate']='2026-10-20'
        market={c:self.cap(c,1000000) for c in ['000001','000002']}
        self.assertEqual(build_representatives('091160',rows,market,'now')['status'],'partial')
if __name__ == '__main__':unittest.main()
