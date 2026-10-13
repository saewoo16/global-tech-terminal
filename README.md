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
