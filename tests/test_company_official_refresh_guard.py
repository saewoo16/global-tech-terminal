import ast, unittest
from pathlib import Path
from unittest.mock import patch, Mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
SOURCE=Path(__file__).resolve().parents[1]/'scripts/update_data.py'
class OfficialRefreshGuard(unittest.TestCase):
 def test_main_cannot_publish_aggregator_quarters_or_advance_financial_check(self):
  tree=ast.parse(SOURCE.read_text()); main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');source=ast.unparse(main)
  self.assertNotIn('fetch_quarters(',source)
  for field in ['quarters','financialCheckedAt','financialUpdated']:
   self.assertNotIn("current['"+field+"'] =",source)
 def test_every_price_path_is_session_gated(self):
  tree=ast.parse(SOURCE.read_text()); functions={n.name:ast.unparse(n) for n in tree.body if isinstance(n,ast.FunctionDef)}
  self.assertIn('completed_daily_points(result)',functions['chart_fallback'])
  self.assertNotIn('.history(',functions['fetch_prices'])
 def test_fetch_prices_uses_only_gated_sources(self):
  from data_quality import clean_prices
  tree=ast.parse(SOURCE.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fetch_prices')
  env={'clean_prices':clean_prices,'chart_fallback':lambda ticker:([['2026-11-06',10]],{}),'latest_completed_daily':lambda ticker:[['2026-11-09',11]]}
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),env)
  self.assertEqual(env['fetch_prices'](Mock(ticker='TEST')),[['2026-11-06',10],['2026-11-09',11]])
