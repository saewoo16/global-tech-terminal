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
