# Trading_tools

BINANCE:BTCUSDT.P 1분봉 단타용 지표 개발 환경.

## 구조

```text
pine/my_indicator.pine   # 트레이딩뷰에 붙여넣을 내 지표 (Pine v6)
tv-api/                  # TradingView 비공식 API (Mathieu2301/TradingView-API)
  src/realtime.js        # 로그인 없이 실시간 1분봉 수신
  src/login.js           # SESSION / SIGNATURE 쿠키 발급
  src/my-indicator.js    # 내 계정에 저장한 지표의 값 실시간 수신
```

## 1. 내 지표를 트레이딩뷰에 적용

1. 트레이딩뷰 차트를 `BINANCE:BTCUSDT.P`, 1분봉으로 설정
2. 하단 **Pine 에디터** → `pine/my_indicator.pine` 내용 붙여넣기
3. **저장** → **차트에 추가**
4. 저장한 지표는 `지표 → 내 스크립트`에 계속 남음

## 2. API로 데이터 받기 (Node.js 18+)

```bash
cd tv-api
npm install
cp .env.example .env

npm run realtime                          # 실시간 캔들 (로그인 불필요)
npm run login -- <이메일> <비밀번호>       # 쿠키 발급 → .env 에 입력
npm run my-indicator                      # 내 지표 값 실시간 수신
```

2FA 계정은 `login`이 실패할 수 있습니다. 브라우저 개발자도구 → 쿠키에서
`sessionid` → `SESSION`, `sessionid_sign` → `SIGNATURE` 로 복사하세요.

## 주의

- 비공식 API: 트레이딩뷰 구조 변경 시 동작이 멈출 수 있고, 약관 위반 소지가 있음
- `.env`(로그인 쿠키)는 절대 커밋 금지 (`.gitignore` 처리됨)
- 실매매 주문은 바이낸스 공식 API 사용 권장
