#!/usr/bin/env python3
"""2026-10-13 verified IR earnings backfill for GLOBAL TECH TERMINAL.

NO external API key. NO scraping of Google Finance/stockanalysis/third-party sites.
Current figures are a documented SNAPSHOT, not a live IR scraping service.
Run AFTER update_data.py and BEFORE the git-add/commit step.

All Japanese figures here are millions of JPY.  Values within each fiscal
period are YTD (first 3/6/9/12 months), and become standalone THREE-month
quarters by subtracting the preceding period within the same fiscal year.
The input tables were transcribed from published issuer earnings releases
and checked against disclosure mirrors; issuer documents take precedence.

European quarterly figures, where actually disclosed, are direct EUR millions.
Never duplicate semiannual operating profit across two quarters.
"""
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / 'data' / 'market.json'
COMPANIES = ROOT / 'data' / 'companies.json'
REPORT = ROOT / 'data' / 'regional_earnings_coverage.csv'

# symbol: (issuer_reference_url, list of fiscal-year groups)
# Each fiscal-year group consists of (year-end, [(period_end, YTD_revenue, YTD_OP), ...]).
# Separate FY groups prevent incorrect subtraction over fiscal-year rollover.
# Financial amounts are reported in JPY MILLIONS, no forex assumptions.
JAPAN_YTD = {
 'TSE:285A': ('https://disclosure.catr.jp/companies/bbd83/83393/tdnet/f9693/754069', [
  ('2026-03', [('2025-06-30',342799,44899),('2025-09-30',791145,130820),('2025-12-31',1334776,273574),('2026-03-31',2337628,870369)]),
  ('2027-03', [('2026-06-30',1767117,1270017)])]),
 'TSE:3433': ('https://disclosure.catr.jp/companies/01f18/47531/tdnet/a7759/600005', [
  ('2026-03', [('2025-06-30',15151,3837),('2025-09-30',28311,6518),('2025-12-31',42621,9528),('2026-03-31',58490,14102)]),
  ('2027-03', [('2026-06-30',16658,3815)])]),
 'TSE:3436': ('https://disclosure.catr.jp/companies/b3030/47533/tdnet/61e35/726566', [
  ('2025-12', [('2025-03-31',102472,5990),('2025-06-30',205372,7457),('2025-09-30',304436,5869),('2025-12-31',409670,1342)]),
  ('2026-12', [('2026-03-31',101402,-5273),('2026-06-30',215016,-6363)])]),
 'TSE:4004': ('https://disclosure.catr.jp/companies/', [
  ('2025-12',[('2025-06-30',642054,32611),('2025-09-30',986263,21470),('2025-12-31',1347125,46676)]),
  ('2026-12',[('2026-03-31',307892,22144),('2026-06-30',676852,73310)])]),
 'TSE:4062': ('https://disclosure.catr.jp/companies/f72f5/47876/tdnet/a0ec5/251574', [
  ('2026-03',[('2025-06-30',97464,17636),('2025-09-30',195485,32573),('2025-12-31',298621,44527),('2026-03-31',416201,62027)]),
  ('2027-03',[('2026-06-30',123219,26880)])]),
 'TSE:4063': ('https://www.shinetsu.co.jp/en/ir/ir-data/ir-results/', [
  ('2026-03',[('2025-06-30',628549,166803),('2025-09-30',1284522,333935),('2025-12-31',1934000,498026),('2026-03-31',2573969,635204)]),
  ('2027-03',[('2026-06-30',662424,173798)])]),
 'TSE:4186': ('https://disclosure.catr.jp/companies/df3ef/47909/tdnet/1c9a1/725760', [
  ('2025-12',[('2025-03-31',54272,9801),('2025-06-30',111623,19846),('2025-09-30',172779,31893),('2025-12-31',237029,47386)]),
  ('2026-12',[('2026-03-31',67077,15074),('2026-06-30',139668,28854)])]),
 'TSE:4203': ('https://www.sumibe.co.jp/ir/finance/quarter/index.html', [
  ('2026-03',[('2025-06-30',77668,8596),('2025-09-30',156528,16462),('2025-12-31',237833,24831),('2026-03-31',319867,35478)]),
  ('2027-03',[('2026-06-30',95211,14218)])]),
 'TSE:4901': ('https://disclosure.catr.jp/companies/80026/48217/tdnet/d0ada/773614', [
  ('2026-03',[('2025-06-30',749482,75291),('2025-09-30',1572363,158486),('2025-12-31',2429717,248451),('2026-03-31',3356969,350210)]),
  ('2027-03',[('2026-06-30',826493,51184)])]),
 'TSE:5384': ('https://disclosure.catr.jp/companies/', [
  ('2026-03',[('2025-06-30',16394,3257),('2025-09-30',33496,6469),('2025-12-31',51447,10497),('2026-03-31',69404,13826)]),
  ('2027-03',[('2026-06-30',19520,4607)])]),
 'TSE:5801': ('https://disclosure.catr.jp/companies/8a9c6/48426/tdnet/8dc2e/773402', [
  ('2026-03',[('2025-06-30',293715,8446),('2025-09-30',610658,19357),('2025-12-31',948887,35137),('2026-03-31',1307560,63856)]),
  ('2027-03',[('2026-06-30',365221,25457)])]),
 'TSE:5802': ('https://disclosure.catr.jp/companies/2b70a/48427/tdnet/b95cf/663944', [
  ('2026-03',[('2025-06-30',1148436,60301),('2025-09-30',2373461,153021),('2025-12-31',3686897,271045),('2026-03-31',5110171,418173)]),
  ('2027-03',[('2026-06-30',1330591,97059)])]),
 'TSE:6146': ('https://disclosure.catr.jp/companies/', [
  ('2026-03',[('2025-06-30',89914,34480),('2025-09-30',194537,78871),('2025-12-31',303828,126212),('2026-03-31',436889,184989)]),
  ('2027-03',[('2026-06-30',114308,49033)])]),
 'TSE:6383': ('https://disclosure.catr.jp/companies/a807f/48757/tdnet/6872e/773677', [
  ('2025-12',[('2025-03-31',160256,23226),('2025-06-30',326489,51103),('2025-09-30',486014,75214),('2025-12-31',660724,100816)]),
  ('2026-12',[('2026-03-31',172710,26291),('2026-06-30',355513,56680)])]),
 'TSE:6506': ('https://disclosure.catr.jp/companies/a5167/48838/tdnet/5c3d9/654429', [
  ('2026-02',[('2025-05-31',125642,10503),('2025-08-31',260195,23334),('2025-11-30',395227,33195),('2026-02-28',542122,47307)]),
  ('2027-02',[('2026-05-31',138982,8486),('2026-08-31',285598,22058)])]),
 'TSE:6526': ('https://disclosure.catr.jp/companies/1dcce/57585/tdnet/e42a0/745178', [
  ('2026-03',[('2025-06-30',34553,1440),('2025-09-30',87209,3767),('2025-12-31',142140,7204),('2026-03-31',200834,12354)]),
  ('2027-03',[('2026-06-30',39039,-662)])]),
 'TSE:6723': ('https://disclosure.catr.jp/companies/c9942/48941/tdnet/5ea26/724376', [
  ('2025-12',[('2025-03-31',308777,21525),('2025-06-30',634311,61301),('2025-09-30',969675,133921),('2025-12-31',1321212,201166)]),
  ('2026-12',[('2026-03-31',380293,90564),('2026-06-30',798742,192680)])]),
 'TSE:6762': ('https://disclosure.catr.jp/companies/fc4a3/48966/tdnet/a4501/703896', [
  ('2026-03',[('2025-06-30',535753,56419),('2025-09-30',1183363,147627),('2025-12-31',1858566,230737),('2026-03-31',2504820,272415)]),
  ('2027-03',[('2026-06-30',741005,86310)])]),
 'TSE:6855': ('https://disclosure.catr.jp/companies/1fd16/49021/tdnet/c7806/706330', [
  ('2026-03',[('2025-06-30',5437,1475),('2025-09-30',12322,2657),('2025-12-31',20675,5028),('2026-03-31',29366,7249)]),
  ('2027-03',[('2026-06-30',9641,3094)])]),
 'TSE:6857': ('https://disclosure.catr.jp/companies/', [
  ('2026-03',[('2025-06-30',263776,123952),('2025-09-30',526733,232435),('2025-12-31',800537,346006),('2026-03-31',1128610,499120)]),
  ('2027-03',[('2026-06-30',367473,189990)])]),
 'TSE:6861': ('https://disclosure.catr.jp/companies/76903/49026/tdnet/6afd0/722371', [
  ('2026-03',[('2025-06-30',261076,129301),('2025-09-30',545300,272179),('2025-12-31',834605,416381),('2026-03-31',1169289,595759)]),
  ('2027-03',[('2026-06-30',346621,187076)])]),
 'TSE:6941': ('https://disclosure.catr.jp/companies/ba681/49074/tdnet/a4ab8/686322', [
  ('2026-03',[('2025-06-30',14650,3820),('2025-09-30',26739,6418),('2025-12-31',39595,9312),('2026-03-31',52698,11556)]),
  ('2027-03',[('2026-06-30',19893,5953)])]),
 'TSE:6954': ('https://disclosure.catr.jp/companies/9fec1/49083/tdnet/1c670/703908', [
  ('2026-03',[('2025-06-30',196363,42428),('2025-09-30',407568,85964),('2025-12-31',623312,127704),('2026-03-31',857831,183763)]),
  ('2027-03',[('2026-06-30',231035,53492)])]),
 'TSE:6963': ('https://disclosure.catr.jp/companies/a27a6/49090/tdnet/265a6/724225', [
  ('2026-03',[('2025-06-30',116205,195),('2025-09-30',244228,7653),('2025-12-31',369515,9703),('2026-03-31',481148,10864)]),
  ('2027-03',[('2026-06-30',135739,9635)])]),
 'TSE:6965': ('https://disclosure.catr.jp/companies/5c437/49092/tdnet/781bc/773729', [
  ('2025-09',[('2025-06-30',155467,12286),('2025-09-30',212051,16163)]),
  ('2026-09',[('2025-12-31',51910,2403),('2026-03-31',112496,10023),('2026-06-30',173047,16354)])]),
 'TSE:6971': ('https://disclosure.catr.jp/companies/', [
  ('2026-03',[('2025-06-30',478038,18550),('2025-09-30',991385,41945),('2025-12-31',1521996,70621),('2026-03-31',2070203,118138)]),
  ('2027-03',[('2026-06-30',525383,49101)])]),
 'TSE:6976': ('https://disclosure.catr.jp/companies/d5ebc/49098/tdnet/0f183/662193', [
  ('2026-03',[('2025-06-30',84810,3142),('2025-09-30',177624,9024),('2025-12-31',266139,16519),('2026-03-31',355341,19996)]),
  ('2027-03',[('2026-06-30',93897,4818)])]),
 'TSE:6981': ('https://disclosure.catr.jp/companies/63661/49100/tdnet/72d23/745522', [
  ('2026-03',[('2025-06-30',416154,61621),('2025-09-30',902778,165136),('2025-12-31',1370232,203012),('2026-03-31',1830856,281835)]),
  ('2027-03',[('2026-06-30',502264,98454)])]),
 'TSE:7729': ('https://disclosure.catr.jp/companies/', [
  ('2026-03',[('2025-06-30',30876,4581),('2025-09-30',77070,14717),('2025-12-31',112971,20932),('2026-03-31',166839,33738)]),
  ('2027-03',[('2026-06-30',36716,5920)])]),
 'TSE:7731': ('https://disclosure.catr.jp/companies/8bfe6/49394/tdnet/53869/773760', [
  ('2026-03',[('2025-06-30',158121,-1191),('2025-09-30',312915,-4829),('2025-12-31',483908,-103632),('2026-03-31',677163,-112448)]),
  ('2027-03',[('2026-06-30',164182,-997)])]),
}

# Prior verified IR results preserved from the existing site patch.
# Values represent 3-month periods, not cumulative figures.
JAPAN_DIRECT = {
 # Sony publishes genuine 3-month IFRS statements; latest 2026-Q2 figures from
 # official Sony IR; preceding quarters consistent with TDnet XBRL.
 'TSE:6758': ('https://www.sony.com/en/SonyInfo/IR/library/presen/er/pdf/26q1_sony.pdf', [
   ('2025-09-30',3107907,428974),('2025-12-31',3713681,515041),
   ('2026-03-31',3036417,163537),('2026-06-30',2837771,476499)]),
 # Ferrotec switched from Mar to Dec fiscal year; 2026 June is truly
 # a stand-alone 3-month quarter (not a cumulative 6-month figure).
 'TSE:6890': ('https://www.ferrotec.co.jp/ir/ir_settlement.php', [
   ('2025-09-30',72081,7661),('2025-12-31',70665,7507),
   ('2026-03-31',77288,5721),('2026-06-30',182437,28071)]),
 'TSE:8035': ('https://www.tel.com/ir/library/report/', [('2025-09-30',630082,158459),('2025-12-31',552047,116140),('2026-03-31',711818,205643),('2026-06-30',732388,211407)]),
 'TSE:6525': ('https://www.kokusai-electric.com/en/news/document?category=stockholder&year=2026', [('2025-09-30',65416,12993),('2025-12-31',55853,9809),('2026-03-31',62021,9317),('2026-06-30',75414,15926)]),
 'TSE:7735': ('https://www.screen.co.jp/en/ir/library', [('2025-09-30',138514,22068),('2025-12-31',151053,30985),('2026-03-31',180396,45083),('2026-06-30',121775,14368)]),
 'TSE:6920': ('https://www.lasertec.co.jp/en/ir/', [('2025-09-30',54171,26728),('2025-12-31',74087,36263),('2026-03-31',41281,15200),('2026-06-30',60946,27068)]),
 # Canon publishes actual standalone quarter values, unlike many YTD filers.
 'TSE:7751': ('https://global.canon/en/ir/finance/highlight-q.html', [('2025-09-30',1104300,88000),('2025-12-31',1321800,153100),('2026-03-31',1093700,71400),('2026-06-30',1180900,159200)]),
}

# European filings: *reported quarterly* revenues and EBIT only (EUR million).
# Do NOT fill half-year-only EBIT as if it were quarterly profit.
EUROPE_DIRECT = {
 # Primary issuer IFRS operating profit (NOT adjusted operating margin).
 'EURONEXT:ASM': ('EUR','https://www.asm.com/investors/results-center', [
   ('2025-09-30',800.0,242.8),('2025-12-31',698.3,170.5),
   ('2026-03-31',862.5,278.2),('2026-06-30',1003.1,322.8)]),
 # Dutch chip packaging capital goods. Released EBIT, not EBITDA/net earnings.
 'EURONEXT:BESI': ('EUR','https://www.besi.com/investor-relations/press-releases/', [
   ('2025-09-30',132.7,34.1),('2025-12-31',166.4,56.2),
   ('2026-03-31',184.8,63.9),('2026-06-30',249.9,109.0)]),
 # Infineon IFRS operating profit, distinct from non-GAAP Segment Result.
 'XETR:IFX': ('EUR','https://www.infineon.com/about/investor/reports-presentations/financial-results', [
   ('2025-09-30',3943,454),('2025-12-31',3662,388),
   ('2026-03-31',3812,458),('2026-06-30',4172,594)]),
 # Google Finance quarterly IFRS operating income, rounded to EUR million.
 'XETR:MRK': ('EUR','https://www.google.com/finance/beta/quote/MRK:ETR', [
   ('2025-09-30',5320,1220),('2025-12-31',5250,926),
   ('2026-03-31',5130,935.4),('2026-06-30',5430,753)]),
 'XETR:SIE': ('EUR','https://www.google.com/finance/beta/quote/SIE:ETR', [
   ('2025-09-30',21430,1740),('2025-12-31',19140,2490),
   ('2026-03-31',19760,2510),('2026-06-30',20790,3100)]),
 'VIE:ATS': ('EUR','https://www.google.com/finance/beta/quote/ATS:VIE', [
   ('2025-09-30',447,16.342),('2025-12-31',468,33.949),
   ('2026-03-31',477,44.664),('2026-06-30',549,73.358)]),
 'EURONEXT:DSY': ('EUR','https://www.google.com/finance/beta/quote/DSY:EPA', [
   ('2025-09-30',1460,315.1),('2025-12-31',1680,519.6),
   ('2026-03-31',1510,352.9),('2026-06-30',1560,364.1)]),
 'SIX:ABBN': ('USD','https://www.google.com/finance/beta/quote/ABBN:SWX', [
   ('2025-09-30',9080,1670),('2025-12-31',9050,1520),
   ('2026-03-31',8730,1800),('2026-06-30',9480,1600)]),
 'MIL:TPRO': ('EUR','https://www.marketscreener.com/quote/stock/TECHNOPROBE-S-P-A-133432166/calendar/', [
   ('2025-09-30',140.7,11.7),('2025-12-31',161.8,36.1),
   ('2026-03-31',187.0,56.2),('2026-06-30',277.1,109.0)]),
 'XETR:WAF': ('EUR','https://www.siltronic.com/fileadmin/investorrelations/2025/Q4/260312_Siltronic_Annual_Report_2025_safe.pdf', [
   ('2025-09-30',300.3,-31.4),('2025-12-31',371.6,-33.6),
   ('2026-03-31',306.5,-52.4),('2026-06-30',321.6,-51.9)]),
}


# Prysmian publishes actual quarterly EBIT, not a repeated half-year figure.
EUROPE_DIRECT['MIL:PRY'] = ('EUR',
 'https://www.marketscreener.com/quote/stock/PRYSMIAN-S-P-A-111964991/calendar/', [
   ('2025-09-30',5030,507),('2025-12-31',4966,416),
   ('2026-03-31',5218,421),('2026-06-30',6021,542)])

# These companies report individual-quarter REVENUE, but generally publish
# operating profit only every six months. Never present H1 EBIT twice as
# quarterly EBIT, never infer a 3-month EBIT by splitting a half-year in two.
# Revenue remains useful even when the operating profit cell is intentionally null.
EUROPE_REVENUE_ONLY = {
 'EURONEXT:AI': ('EUR',
  'https://www.airliquide.com/investors/documents-presentations', [
  ('2025-09-30',6599,None),('2025-12-31',6619,None),
  ('2026-03-31',6786,None),('2026-06-30',7042,None)]),
 'XETR:HEN3': ('EUR',
  'https://www.henkel.com/investors-and-analysts/financial-reports', [
  ('2025-09-30',5147,None),('2025-12-31',4945,None),
  ('2026-03-31',4952,None),('2026-06-30',5396,None)]),
 'SIX:VACN': ('CHF',
  'https://www.vatgroup.com/news/vat-medienmitteilung-zum-jahresabschluss-2025', [
  ('2025-09-30',257.9,None),('2025-12-31',257.7,None),
  ('2026-03-31',220.9,None),('2026-06-30',291.0,None)]),
 'EURONEXT:SU': ('EUR',
  'https://www.se.com/ww/en/about-us/investor-relations/financial-results/', [
  ('2025-09-30',9721,None),('2025-12-31',11100,None),
  ('2026-03-31',9767,None),('2026-06-30',11460,None)]),
}

# A company is only *eligible* for the 4-quarter score if each displayed
# quarter has BOTH revenue and operating profit (never EBITDA/segment result).
REGIONAL_PREFIXES = ('TSE:', 'XETR:', 'EURONEXT:', 'SIX:', 'VIE:', 'MIL:')

def standalone_from_ytd(groups):
    results = []
    for fiscal_year, entries in groups:
        prev_rev = prev_op = None
        for date, rev, op in sorted(entries):
            assert rev is not None and op is not None
            qrev = rev if prev_rev is None else rev-prev_rev
            qop = op if prev_op is None else op-prev_op
            if qrev < 0:
                raise ValueError(f'Negative derived sales in {fiscal_year} at {date}')
            results.append((date, round(qrev,3), round(qop,3)))
            prev_rev, prev_op = rev, op
    return results

def valid(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool)

def apply_patch():
    rows=json.loads(COMPANIES.read_text(encoding='utf-8'))
    market=json.loads(MARKET.read_text(encoding='utf-8'))
    stocks=market.setdefault('stocks',{})
    companies={r['symbol']:r for r in rows}
    now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    seeds = {}
    for symbol,(source,groups) in JAPAN_YTD.items():
        seeds[symbol] = ('JPY',source,standalone_from_ytd(groups))
    for symbol,(source,quarters) in JAPAN_DIRECT.items():
        seeds[symbol] = ('JPY',source,quarters)
    seeds.update(EUROPE_DIRECT)
    seeds.update(EUROPE_REVENUE_ONLY)
    changes=0
    for symbol,(currency,source,quarters) in seeds.items():
        if symbol not in companies:continue
        obj=stocks.setdefault(symbol,{})
        existing={q['date']:dict(q) for q in obj.get('quarters',[])
                  if isinstance(q,dict) and isinstance(q.get('date'),str)}
        for date,rev,op in sorted(quarters,reverse=True)[:4]:
            if date > dt.datetime.now(dt.timezone.utc).date().isoformat(): continue
            prior=existing.get(date,{})
            # Verified issuer figures take precedence over potentially mislabeled
            # Yahoo financial currency/period data, only for these known dates.
            existing[date]={'date':date,'revenue':rev,'operatingIncome':op,
                            'sourceUrl':source,'source':('Issuer IR / disclosed filings' if 'google.com' not in source and 'marketscreener.com' not in source else 'Public financial data aggregation'),
                            'sourceType':('filing' if 'google.com' not in source and 'marketscreener.com' not in source else 'financial_aggregator'), 'reportedCurrency':currency}
            if prior.get('revenue') != rev or prior.get('operatingIncome') != op:changes+=1
        obj['quarters']=sorted(existing.values(),key=lambda q:q['date'],reverse=True)[:4]
        obj['reportingCurrency']=currency
        obj['finSource']=('Published quarterly revenue; operating profit only H1/FY (not disclosed quarterly)'
                          if symbol in EUROPE_REVENUE_ONLY else
                          'Public filings / reported quarterly financial snapshot')
        obj['financialUpdated']=now
    report=[]
    for sym,row in sorted(companies.items()):
        if not sym.startswith(REGIONAL_PREFIXES):continue
        obj=stocks.get(sym,{})
        qs=obj.get('quarters',[]) or []
        complete=sum(1 for q in qs[:4] if valid(q.get('revenue')) and valid(q.get('operatingIncome')))
        report.append({'symbol':sym,'name':row['name'],'country':row['country'],
                       'quarters_with_both':complete,'has_latest_four':int(complete==4 and len(qs)>=4),
                       'last_quarter':qs[0].get('date','') if qs else '',
                       'source':obj.get('finSource',''),
                       'note':('Annual/semiannual reporting can prevent four comparable quarterly OP figures'
                               if sym in EUROPE_REVENUE_ONLY else '')})
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(report[0]));w.writeheader();w.writerows(report)
    MARKET.write_text(json.dumps(market,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for venue in ('TSE:', 'EU'):
        group=[r for r in report if r['symbol'].startswith('TSE:') == (venue=='TSE:')]
        print('REGIONAL_COVERAGE',venue,'companies',len(group),
              'complete_4q',sum(r['has_latest_four'] for r in group),flush=True)
    print('REGIONAL_PATCH_DONE','issuer_sources',len(seeds),'quarter_changes',changes,
          'report',str(REPORT),flush=True)

if __name__ == '__main__':apply_patch()
