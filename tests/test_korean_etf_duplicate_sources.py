"""Reject source duplicates without choosing prices or changing session identity."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import update_korean_etf_charts as collector


class DuplicateSourceTests(unittest.TestCase):
    def inputs(self, kind=None, conflicting=False):
        daily=['20261105|100|110|90|100|10', '20261106|100|110|90|101|20']
        points=[{'localDateTime':'202611061500','currentPrice':100,'accumulatedTradingVolume':10},
                {'localDateTime':'202611061501','currentPrice':101,'accumulatedTradingVolume':20}]
        if kind=='daily':
            daily.append('20261106|100|110|90|102|30' if conflicting else daily[-1])
        if kind=='intraday':
            point=dict(points[-1])
            if conflicting:point.update(currentPrice=102,accumulatedTradingVolume=30)
            points.append(point)
        xml=('<protocol><chartdata origintime="20200101">'+''.join(f'<item data="{r}"/>' for r in daily)+'</chartdata></protocol>').encode()
        intraday=json.dumps({'tradeBaseAt':'20261106','stockExchangeType':'KRX','marketStatus':'CLOSE','priceInfos':points}).encode()
        return xml,intraday

    def build(self, kind=None, conflicting=False, code='091160'):
        with patch.object(collector,'fetch',side_effect=self.inputs(kind,conflicting)):
            return collector.build_fund((code,'test','industry'),{code:{'itemname':'KODEX test'}},dt.date(2026,11,8))

    def test_identical_and_conflicting_daily_duplicates_rejected(self):
        for conflicting in (False,True):
            with self.subTest(conflicting=conflicting),self.assertRaisesRegex(ValueError,'091160 daily: duplicate source date 2026-11-06'):
                self.build('daily',conflicting)

    def test_identical_and_conflicting_intraday_duplicates_rejected(self):
        for conflicting in (False,True):
            with self.subTest(conflicting=conflicting),self.assertRaisesRegex(ValueError,'091160 intraday: duplicate source time 2026-11-06T15:01:00'):
                self.build('intraday',conflicting)

    def test_distinct_funds_can_share_dates_and_times(self):
        first=self.build(code='091160');second=self.build(code='139260')
        self.assertEqual(first['daily'],second['daily'])
        self.assertEqual(first['intraday']['points'],second['intraday']['points'])
        self.assertEqual([p['volume'] for p in first['intraday']['points']],[10,10])
        self.assertEqual([p['close'] for p in first['daily']],[100,101])

    def test_actual_main_retains_previous_prices_for_each_duplicate_kind(self):
        old=self.build()
        old['selectionEvidence']={'asOf':'2026-11-05','note':'preserve evidence'}
        for kind in ('daily','intraday'):
            for conflicting in (False,True):
                with self.subTest(kind=kind,conflicting=conflicting),tempfile.TemporaryDirectory() as tmp:
                    dest=Path(tmp)/'snapshot.json';dest.write_text(json.dumps({'funds':[old]}))
                    xml,intraday=self.inputs(kind,conflicting)
                    def fetch(url):
                        if url==collector.CATALOGUE:return json.dumps({'result':{'etfItemList':[{'itemcode':'091160','itemname':'KODEX test'}]}}).encode()
                        return xml if 'fchart.stock' in url else intraday
                    # Portfolio refresh is independent of price collection and is not under test.
                    with patch.object(collector,'UNIVERSE',[('091160','test','industry')]),patch.object(collector,'fetch',side_effect=fetch),patch.object(collector,'refresh_representatives'),patch.object(sys,'argv',['collector','--output',str(dest)]):
                        collector.main()
                    result=json.loads(dest.read_text());retained=result['funds'][0]
                    expected=copy.deepcopy(old);expected.update(refreshStatus='stale',refreshError=result['errors'][0]['error'])
                    self.assertEqual(retained,expected)
                    self.assertEqual(len(result['errors']),1)
                    self.assertIn('duplicate source',result['errors'][0]['error'])

    def test_no_previous_snapshot_is_not_replaced_with_duplicate_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'snapshot.json';before='{"funds": []}\n';dest.write_text(before)
            with patch.object(collector,'UNIVERSE',[('091160','test','industry')]),patch.object(collector,'fetch',return_value=b'{"result":{"etfItemList":[]}}'),patch.object(collector,'build_fund',side_effect=ValueError('duplicate source date')),patch.object(collector,'refresh_representatives'),patch.object(sys,'argv',['collector','--output',str(dest)]):
                with self.assertRaisesRegex(RuntimeError,'existing output preserved'):collector.main()
            self.assertEqual(dest.read_text(),before)


if __name__=='__main__':unittest.main()
