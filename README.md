# Global Tech Terminal

글로벌 테크 기업 246개(259개 업종 매핑) 연구용 대시보드. GitHub Pages에서 모바일과 PC로 접근합니다.

## 1. 설치·배포
1. GitHub에서 새 **Public** repository를 `global-tech-terminal` 이름으로 생성합니다.
2. 이 ZIP 파일의 **내부 파일/폴더**(`index.html`, `data/`, `scripts/`, `.github/`, `requirements.txt`)을 저장소 **루트**에 업로드합니다. 숨김 폴더 `.github`가 빠지면 자동 갱신이 되지 않습니다. 파일 수가 많거나 숨김 폴더 업로드가 어려우면 GitHub Desktop으로 업로드합니다.
3. 저장소의 `Settings → Pages → Build and deployment`에서 `Deploy from a branch`, `main`, `/(root)`를 선택하고 저장합니다.
4. 배포 URL은 `https://GITHUB_USERNAME.github.io/global-tech-terminal/` 형태입니다. (실제 이름으로 바꿔야 합니다.)
5. `Settings → Actions → General → Workflow permissions`에서 `Read and write permissions`를 허용합니다. 조직/계정 정책상 막혀 있으면 관리자 설정이 필요합니다.
6. `Actions → Update market data → Run workflow`를 눌러 **첫 수집**을 진행합니다. `data/market.json`에 갱신된 데이터를 커밋하면 대시보드에 표시됩니다.
7. 이후 평일 하루 1회 자동 실행되도록 되어 있습니다. GitHub Actions 스케줄 실행은 지연되거나 정책상 비활성화될 수 있습니다.

## 2. 주가 차트가 비어 있을 때
네이버 차트 이미지나 TradingView 임베드 대신 일별 **실제 종가를 자체 차트**로 표시합니다. 일본 Kioxia (`285A.T`), 한국 SK hynix (`000660.KS`) 등 거래소별 코드를 수집기에 매핑했습니다. 일부 종목은 Yahoo Finance에서 데이터를 제공하지 않거나 호출을 제한할 수 있으며, 오류 시 빈 차트와 TradingView/Google Finance 원본 링크가 표시됩니다. 샘플/가상 시세는 넣지 않았습니다.

## 3. 실적
최근 4개 분기의 *분기 매출액*, *분기 영업이익*을 백만 **보고 통화** 단위로 표시합니다. OPM은 자동 계산합니다. 주가·시총은 가능한 경우 평일 갱신하고 실적 조회는 기본적으로 월요일/수동 실행 때만 시도합니다. 자산/사업 구조에 따라 영업이익 라인이 공급사 데이터에 없을 수 있습니다. 공시 원문과 비교 검증이 필요한 연구용 2차 데이터입니다.

## 4. 중요 제약
- Yahoo Finance/yfinance는 무료·비공식 데이터 경로이며 API 제한, 결측 및 약관 문제가 발생할 수 있습니다. 246개 종목에 대한 안정적 상업적 이용이 필요하면 적법한 유료 공급사로 교체해야 합니다.
- GitHub Actions 실행 시간이 길어지거나 429 오류가 나면 일부 종목은 이전 데이터로 남습니다. 각 종목의 `updated` 필드를 함께 보관합니다.
- 비미국 종목의 `marketCap` 보고 통화 환산 실패 시 임의 값 대신 빈칸을 둡니다.
- 미국 시장이 아닌 종목은 일부 티커가 잘못 매핑되었을 수 있습니다. `scripts/update_data.py`의 `lookup()`을 수정하세요.
- GitHub Pages는 공개 사이트입니다. 비밀번호나 비공개 API 키를 저장소에 넣지 마세요.

## 5. 다음 수정
`index.html`의 디자인과 `data/companies.json`의 기업/산업 목록을 수정 후 같은 GitHub 저장소에 커밋하면 **동일 URL이 유지**됩니다. 기업의 속성(티커/나라/분류)이 바뀌면 데이터 수집기 매핑도 같이 확인하세요.

## 6. 데이터 품질 관리 (2026-10-17 정비)

- 246개 회사 전체의 차트·시총·분기 실적을 `data/coverage.json`과 `data/coverage.csv`에서 검사합니다. 차트와 시총은 246개 모두 확보했습니다.
- 240개 회사는 최근 4개 분기 매출/영업이익이 있습니다. Air Liquide, Schneider Electric, VAT, Henkel은 분기 매출은 있지만 영업이익은 반기·연간만 공시합니다. Kingboard Laminates는 반기·연간 공시 회사로 실제 반기 실적을 별도 표시합니다. DuPont은 연결 GAAP 영업이익 소계를 별도 제시하지 않으므로 검증된 계속영업 매출만 표시합니다. N/A는 0이 아닙니다.
- Everpure(구 Pure Storage)는 `NYSE:P`, Fiserv는 `NASDAQ:FISV`, LX Semicon은 KOSPI의 `108320.KS`로 수정했습니다. 이전 심볼은 마이그레이션합니다.
- 새로 보완한 실적의 공시 URL·기간·단위·확인일·파생 계산 근거는 `data/financial_backfill_asia.json`과 `data/financial_backfill_us.json`에 보관합니다. 이 파일들은 출처를 확인한 시점의 스냅샷이며 실시간 공시 수집기가 아닙니다. 기존 모든 회사의 모든 값에 대해 독립 감사가 이뤄졌다는 의미는 아닙니다.
- 시세 갱신일과 실적 확인일은 별개입니다. 정적 공시 스냅샷을 다시 적용해도 확인일을 오늘로 바꾸지 않습니다. 원문에서 반기 누적 실적만 공시한 경우 이를 임의로 2분기에 나누지 않습니다.
- 무료 시세 공급사의 일시 실패 시 기존 유효값을 보존하며, 모든 시세 요청이 실패하면 갱신을 성공으로 발표하지 않습니다. 조정종가용 대체 엔드포인트, 환율 조회 캐시, 원자적 JSON 저장, 전체 회사 회귀 검사를 사용합니다.
- 시총은 공급사 값입니다. LX Semicon의 최초 복구값은 최신 종가 × 회사가 공개한 발행주식수로 산출 후 USD/KRW로 환산한 값이며 화면에서 계산값으로 표시합니다. 모든 시총은 최신 실시간 값이 아닐 수 있으므로 표시된 기준일을 확인하세요.

### 로컬 검증

```sh
python -m unittest discover -s tests -v
python scripts/apply_financial_backfills.py
python scripts/audit_coverage.py
```

스케줄은 기존 평일 22:00 UTC(한국시간 다음 날 07:00)를 유지합니다. 수동 실행은 실적도 다시 요청합니다. 파이프라인은 테스트 → 시세/실적 수집 → 공시 보완 → 전체 커버리지 검사 → 데이터 커밋 순서입니다. 같은 회사의 유효 차트·시총을 잃거나 같은 보고 기간의 실적 커버리지가 감소하면 게시를 중단합니다. 신규 분기의 일부 항목 누락은 점검표에 기록합니다.

## 7. 마감 브리핑 아카이브

상단 **기업 탐색 / 마감 브리핑** 탭으로 전환합니다. 기존 기업별 차트·실적은 그대로 유지됩니다. `#briefing/US/2026-10-16`처럼 시장·현지 거래일을 포함한 링크를 공유할 수 있습니다. 날짜 선택지는 검증 후 게시한 날짜만 표시하며, 다른 시장으로 바꾸면 같은 날짜가 있을 때 유지합니다.

- 핵심 시황과 지수를 먼저 표시합니다. 업종 비교표는 기본 펼침 상태이며, **1일 / 1주 / 1개월** 열을 눌러 오름차순·내림차순으로 정렬합니다. 대분류/세부업종 그룹 안에서 정렬합니다.
- ETF 또는 대표 종목 바스켓을 사용한 경우 각 행에 지표명과 구성 기준을 표시합니다. 순수 업종지수나 전체 업종 전수조사를 의미하지 않습니다.
- 한국 수급, 이례적 등락, 신고가, 실적/컨퍼런스콜은 세부항목을 펼쳐 확인합니다. 빈 항목은 미확인이며 해당 사례 없음으로 표현하지 않습니다.
- 2026-10-16 기업 신고가·이례적 등락 선별 범위는 미국 시총 상위 500개, 한국 300개로 확대했습니다. 미국 당일 일봉 500개/52주 전체 이력 490개, 한국 당일 일봉 299개/52주 전체 이력 294개를 확인했습니다. 한국 삼부토건은 거래량 0·정체 시세로 미검증입니다. 상장 이력이 짧은 종목은 52주 신고가로 단정하지 않습니다. 모집단은 10/17 조회한 제공사 대표 상장 최신 스냅샷이며 10/16 종가 시점고정 순위가 아닙니다. 실제 거래대금은 미확보이며 거래량으로 대체하지 않습니다. 실적·컨퍼런스콜 확인 범위와는 별개입니다. `screeningCoverage`에 요청·선별·유효·결측·52주 이력·거래량/거래대금 커버리지를 별도로 저장합니다.
- 미국/한국 시황은 현지 거래일 기준입니다. 같은 날짜의 한국장은 미국장보다 먼저 마감합니다. 실적 발표일, 시황 반응일, 콜 원문 확인 여부를 구분합니다.

### 데이터 구조와 매일 추가하기

`data/briefings.json`은 `schemaVersion: 1`, `updatedAt`, `entries`로 구성합니다. 각 entry의 고유 키는 `market` (`US`/`KR`) + `date` (`YYYY-MM-DD`)입니다. 필수값은 `status` (`partial`/`complete`), `title`, `sources`입니다. 확인하지 못한 숫자는 `null`로 두고, 공백·0·추정치로 대체하지 않습니다.

선택 섹션:

- `summary`: `{title, text, sourceIds}` 배열, `indices`: `{name, close, changePct, sourceIds}` 배열
- `sectors`: `{methodology, note, rows}`. 각 행은 `{name, ticker, benchmark, group, day, week, month, sourceIds}`. 수익률은 백분율 숫자입니다.
- ETF 행은 `instrumentType: "etf"`, 바스켓은 `"basket"`으로 구분합니다. ETF에는 `holdings: {status:"verified", asOf:"YYYY-MM-DD", sourceIds:[], top5:[{name,ticker,weightPct}]}`를 추가합니다. 운용사 실제 보유내역 기준일·출처와 비중 내림차순의 정확히 5개 보유종목을 기록하며 `티커(종목1 / 종목2 / 종목3 / 종목4 / 종목5)` 형식으로 표시하며 중복되는 ETF 풀네임과 행별 보유비중·기준일·출처 줄은 생략합니다. 실제 기준일과 출처는 하단 출처 목록과 데이터에 보존합니다. 현재 자료를 과거 거래일 자료로 간주하지 않습니다. 확인하지 못한 경우 `{status:"unverified", note:"미확인 이유"}`로 명시하고 추정 종목을 넣지 않습니다. 기존 3종목 바스켓은 ETF 상위 5종목으로 바꾸지 않습니다. 매일 새 브리핑 작성 때 기준일과 출처를 다시 검증하며 이전 보유내역의 날짜를 자동으로 오늘로 바꾸지 않습니다.
- `movers` / `highs`: `{criteria, note, rows}`. 각 행은 `{name, ticker, changePct, marketCapUSD, reason, kind, sourceIds}`. 거래량 검증값은 `volumeCurrent`, `volumePrevious`, `volumeChangePct`에 기록합니다.
- `earnings`: `{note, rows}`. 각 행은 `{name, ticker, period, summary, metrics:[{label,value}], callHighlights:[], sourceIds}`. `callHighlights`에는 확인한 자료 유형을 명시합니다.
- `flows`: `{unit, asOf, note, sourceIds, rows:[{market, foreign, institution, individual}]}`. 양수는 순매수입니다.
- `watchlist` / `limitations`: 문자열 배열
- `sources`: `{id, title, url, note}` 배열. 모든 `sourceIds`는 같은 entry의 source ID를 참조합니다.

검증된 단일 entry 또는 여러 entries가 든 같은 구조의 JSON 파일을 준비한 뒤:

```sh
python scripts/manage_briefings.py --entry /path/to/verified-entry.json
python scripts/manage_briefings.py
python -m unittest discover -s tests -v
node tests/test_ui.cjs
node tests/test_briefing_ui.cjs
```

추가 도구는 같은 시장·날짜만 교체하고 과거 날짜와 다른 시장을 보존합니다. 유효하지 않은 날짜, 중복 날짜, 잘못된 출처 링크, 존재하지 않는 source ID, 무한대·NaN·숫자 문자열은 거부합니다. 검증 후 원자적으로 저장합니다. GitHub `main`에 검증된 변경을 커밋하면 기존 Pages URL에 반영됩니다.

이 UI 추가만으로 뉴스·컨퍼런스콜을 자동 생성하거나 새로운 일일 스케줄을 켜지는 않습니다. 별도로 승인된 수집 작업은 검증된 entry를 위 방식으로 추가할 수 있습니다. 기존 시세 자동 수집은 브리핑 내용/날짜를 바꾸지 않습니다. 기존 Actions 테스트 단계에 브리핑 검사도 포함했습니다.


## 10. 시장 히트맵 · 금리/매크로 탭

- `#heatmap`: FINVIZ가 제공하는 공식 Maps 임베드 (`https://finviz.com/widgets/map?t=sec&st=d1&theme=dark`)로 S&P 500 업종별 1일 등락률을 표시합니다. 원본 페이지는 iframe 제한이 있으므로 넣지 않습니다. 원본 링크를 항상 함께 제공합니다.
- `#rates`: 공개 이용 가능한 FRED 차트를 2열(모바일 1열)로 모읍니다. 조회 시점 UTC 날짜부터 5년 전까지의 원본 PNG 차트를 사용하며, 조회 종료일을 데이터 최신 관측일이라고 표시하지 않습니다. 원본 제목·축·출처·로고를 유지하고 시리즈 링크, 단위, 빈도를 표시합니다. 매 방문 시 원본 제공자가 제공하는 이미지이므로 별도 API 키나 저장소 내 시계열 복제가 없습니다.
- 미국 10년 국채는 DGS10(%/일별), 10년 우량 회사채는 HQMCB10YRP(%/월별, AAA·AA·A 등급 액면수익률)입니다. 후자는 전체 투자등급 회사채 지수 수익률과 동일하지 않습니다. 별도로 ICE 전체 투자등급 원본 링크를 제공합니다.
- WTI와 Brent는 DCOILWTICO/DCOILBRENTEU 현물 가격(USD/배럴)이며 선물이 아닙니다. DEXJPUS/DEXKOUS는 각각 엔/1 USD, 원/1 USD입니다. 환율은 일별 관측이지만 공개 시차가 있습니다.
- 달러지수 차트는 연준의 교역 가중 광의 달러지수 DTWEXBGS(2006년 1월=100)입니다. ICE DXY와 구성·기준이 다르며 DXY로 표기하지 않습니다. DXY는 공급사 위젯에서 표시할 수 없음을 확인하여 별도 TradingView 원본 링크만 제공합니다.
- ICE 하이일드 스프레드(BAMLH0A0HYM2)·수익률(BAMLH0A0HYM2EY)은 공개 재게시 권한을 확인하지 않았으므로 원본 FRED 링크만 제공합니다. 차트나 데이터를 재게시하지 않습니다. FRED에 수록되어 있다는 사실만으로 모든 시리즈가 공개 재배포 가능한 것은 아닙니다.
- 외부 차트는 제공사 장애·네트워크·브라우저 설정에 따라 표시되지 않을 수 있습니다. 오류 안내·차트 다시 불러오기·직접 원본 링크를 유지하며 임의 값/가짜 차트로 채우지 않습니다. FRED가 HTTP 200으로 빈 이미지를 반환할 수 있어, 화면이 비어도 오류로 감지되지 않는 경우에는 다시 불러오기/원본을 이용합니다. 지표별 시차와 주기 때문에 같은 기준일의 실시간 수치가 아닙니다.
- 접근성: 네 탭은 방향키/Home/End 탐색, ARIA 선택 상태, 개별 해시 링크와 뒤로/앞으로 이동을 지원합니다. 기존 기업 선택/검색/브리핑 상태는 유지됩니다.

추가 회귀 검사: `node tests/test_markets_ui.cjs`.
공식 안내: [FINVIZ 임베드](https://finviz.com/blog/you-can-now-embed-finviz-maps-on-your-website-blog-or-app/), [FRED 공유/임베드](https://fred.stlouisfed.org/help/graphs/share-my-fred-graph/how-to-embedding-fred-graphs).

### FINVIZ 기간별 원본 링크 (2026-10-17)

시장 히트맵의 기존 1일 임베드 아래에 **1주일 맵 / 1개월 맵** 원본 열기 버튼을 추가했습니다. 사용자 지정 URL `https://finviz.com/map?st=w1`, `https://finviz.com/map?st=w4`는 각각 S&P 500 1주일/1개월 뷰임을 공식 사이트에서 확인했습니다. 새 탭으로 열며 외부 링크 보호 속성을 적용했습니다. 원본 조회는 무료이지만 공식 임베드 설정의 기간 선택은 Elite로 제한되어 있으므로 주간·월간 iframe은 추가하지 않습니다.
