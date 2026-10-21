from email.message import Message
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kofia_official import collect

# Minimal fixture preserves observed JSP structure: <head>...<body>...</body>,
# no outer HTML tag. Public runner evidence: 2026-10-21, 48,223 bytes.
BODY='''<head><title>메인 | 자본시장통계, FreeSIS</title></head><body>
<dl>투자자예탁금 <dd>백만원 | 10/20</dd><dd>90,297,588</dd></dl>
<dl>신용융자 <dd>백만원 | 10/20</dd><dd>30,513,862</dd></dl>
<p>[2026-10-20] 신용공여통계관리 통계가 발표되었습니다.</p>
<footer>금융투자협회</footer><script>var popupItemCount = 8;</script></body>'''

class Response:
    status=200
    def __init__(self,text):
        self.raw=text.encode();self.headers=Message()
        self.headers['Content-Type']='text/html; charset=UTF-8'
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return self.raw

class DocumentBoundary(unittest.TestCase):
    def acquire(self,first,second):
        with patch('kofia_official.urllib.request.urlopen',side_effect=[Response(first),Response(second)]),patch('builtins.print'):
            return collect('2026-10-21T17:50:00+09:00')
    def test_complete_body_without_outer_html(self):
        result=self.acquire(BODY,BODY)
        self.assertEqual(result['date'],'2026-10-20');self.assertEqual(result['officialInvestorDeposits'],90297588)
    def test_truncated_https_falls_back_complete_http(self):
        result=self.acquire(BODY[:BODY.index('<p>')]+'<a href="/stat/',BODY)
        self.assertEqual(result['transport'],'http');self.assertEqual(result['officialMarginLoans'],30513862)
    def test_missing_body_end_fails_even_with_full_statistics(self):
        with self.assertRaises(ValueError):self.acquire(BODY.replace('</body>',''),BODY.replace('</body>',''))
    def test_mismatched_dates_still_fail(self):
        invalid=BODY.replace('10/20','10/21',1)
        with self.assertRaises(ValueError):self.acquire(invalid,invalid)
    def test_content_length_mismatch_still_fails(self):
        r=Response(BODY);r.headers['Content-Length']=str(len(r.raw)+10)
        with patch('kofia_official.urllib.request.urlopen',side_effect=[r,r]),patch('builtins.print'):
            with self.assertRaises(ValueError):collect('2026-10-21T17:50:00+09:00')
