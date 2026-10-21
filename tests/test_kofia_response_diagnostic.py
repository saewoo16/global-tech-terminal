from email.message import Message
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from kofia_official import response_diagnostic

class DiagnosticTests(unittest.TestCase):
    def test_reports_fragment_without_accepting_it(self):
        h=Message();h['Content-Type']='text/html; charset=utf-8';h['Content-Length']='43'
        result=response_diagnostic('<body>투자자예탁금 신용융자 신용공여통계관리</body>'.encode(),h)
        self.assertFalse(result['hasHtmlEnd']);self.assertTrue(result['hasBodyEnd'])
        self.assertTrue(result['hasAnnouncement']);self.assertEqual(len(result['sha256']),64)
    def test_redacts_input_query_and_opaque_values(self):
        h=Message();h['Set-Cookie']='secret-session'
        raw=b'<input value="secret123"><a href="https://example.com/?token=secret123">abcdefghijklmnopqrstuvwxyz0123456789</a>'
        result=response_diagnostic(raw,h)
        self.assertNotIn('secret123',result['prefix']);self.assertNotIn('secret-session',str(result))
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz0123456789',result['prefix'])
