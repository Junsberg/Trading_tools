# Trading_tools

BINANCE:BTCUSDT.P 5분봉 단타용 커스텀 지표 개발 환경.

목표: API로 과거 구간 백테스트를 반복하며 지표를 완성 → 트레이딩뷰에 커스텀 지표로 적용 → 신호(알림 웹훅)로 자동매매.

## 구조

```text
pine/my_indicator.pine   # 실전 차트용 지표 (알림 웹훅 포함)
pine/my_strategy.pine    # 백테스트용 strategy 버전 (신호 로직은 지표와 동일하게 유지)
tv-api/                  # TradingView 비공식 API (Mathieu2301/TradingView-API)
  src/realtime.js        # 로그인 없이 실시간 봉 수신
  src/login.js           # SESSION / SIGNATURE 쿠키 발급
  src/my-indicator.js    # 내 계정에 저장한 지표의 값 실시간 수신
  src/backtest.js        # 내 계정에 저장한 strategy 의 백테스트 리포트 수신 → reports/*.json
```

## 등급 제한과 우회

| 작업 | 트레이딩뷰 UI (에센셜) | API |
|---|---|---|
| 실시간 봉 | 됨 | 로그인 없이 됨 |
| 전략 테스터 날짜 지정 | 안 됨 (당일만) | `--to 날짜 --range N` (내부적으로 리플레이 세션 사용) |
| 리포트 압축 형식 | - | 트레이딩뷰가 zlib 로 바꿔서 `src/tv.js` 래퍼로 대응 |
| Pine 스터디 로드 | 됨 | **로그인 필수** (익명은 스터디 한도 0) |
| 봉 개수 | 등급 한도 (에센셜 1만 봉 ≈ 5분봉 35일) | 동일 한도 적용 |

장기(수개월 이상) 백테스트는 바이낸스 공식 데이터로 따로 하는 게 정확하다.

## 1. Pine 스크립트를 내 계정에 저장

1. 트레이딩뷰 차트를 `BINANCE:BTCUSDT.P`, 5분봉으로 설정
2. 하단 **Pine 에디터** → `pine/my_strategy.pine` 붙여넣기 → **저장** (이름 `My Scalping Strategy`)
3. 같은 방법으로 `pine/my_indicator.pine` 저장 (이름 `My Scalping Indicator`) → **차트에 추가**
4. 저장한 스크립트는 `지표 → 내 스크립트`에 남고, API가 이 이름으로 찾는다

## 2. API 설정 (Node.js 18+)

```bash
cd tv-api
npm install
cp .env.example .env
npm run login -- <이메일> <비밀번호>   # 출력된 SESSION / SIGNATURE 를 .env 에 입력
```

2FA 계정은 `login`이 실패할 수 있다. 브라우저 개발자도구 → Application → Cookies → tradingview.com 에서
`sessionid` → `SESSION`, `sessionid_sign` → `SIGNATURE` 로 복사한다.

## 3. 실행

```bash
npm run realtime                                   # 실시간 봉 (로그인 불필요)
npm run backtest                                   # 최근 5000봉 백테스트 (.env 의 STRATEGY_NAME)
npm run backtest -- --to 2026-09-01 --range 5000   # 2026-09-01 까지의 5000봉
npm run backtest -- --tf 15                        # 타임프레임 변경
npm run my-indicator                               # 지표 값(Signal, RSI 등) 실시간 수신
```

백테스트 결과는 콘솔 요약 + `tv-api/reports/*.json` (성과·거래 목록·에쿼티 곡선).

## 리페인팅 없는 지표 원칙

```pine
// 1. 확정된 봉에서만 신호 발생
longSignal = ta.crossover(fastEma, slowEma) and barstate.isconfirmed

// 2. 상위 타임프레임 참조 시 lookahead 금지 + 확정봉 사용
htf = request.security(syminfo.tickerid, "15", close[1], lookahead = barmerge.lookahead_off)

// 3. strategy() 에서 calc_on_every_tick = false (기본값 유지)
```

알림은 **봉 마감 시 1회(Once Per Bar Close)** 로 생성한다.

## 주의

- 비공식 API: 트레이딩뷰 구조 변경 시 동작이 멈출 수 있고, 약관 위반 소지가 있음
- `.env`(로그인 쿠키)는 절대 커밋 금지 (`.gitignore` 처리됨)
- 실매매 주문은 바이낸스 공식 API 사용 권장
