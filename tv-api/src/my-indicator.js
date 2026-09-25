// 내 트레이딩뷰 계정에 저장된 개인 지표(Pine)의 값을 실시간으로 수신
require('dotenv').config();
const TradingView = require('./tv'); // zlib 리포트 대응 래퍼

const { SESSION, SIGNATURE } = process.env;
const SYMBOL = process.env.SYMBOL || 'BINANCE:BTCUSDT.P';
const TIMEFRAME = process.env.TIMEFRAME || '1';
const INDICATOR_NAME = process.env.INDICATOR_NAME || 'My Scalping Indicator';

if (!SESSION || !SIGNATURE) {
  console.error('.env 에 SESSION, SIGNATURE 를 설정하세요 (npm run login 참고)');
  process.exit(1);
}

(async () => {
  const list = await TradingView.getPrivateIndicators(SESSION, SIGNATURE);
  const found = list.find((i) => i.name === INDICATOR_NAME);
  if (!found) {
    console.error(`"${INDICATOR_NAME}" 지표를 찾지 못했습니다. 내 지표 목록:`);
    list.forEach((i) => console.error(' -', i.name));
    process.exit(1);
  }

  const client = new TradingView.Client({ token: SESSION, signature: SIGNATURE });
  const chart = new client.Session.Chart();
  chart.setMarket(SYMBOL, { timeframe: TIMEFRAME, range: 100 });
  chart.onError((...err) => console.error('Chart error:', ...err));

  const study = new chart.Study(await found.get());
  study.onError((...err) => console.error('Indicator error:', ...err));
  study.onReady(() => console.log(`지표 "${found.name}" 로드 완료`));

  study.onUpdate(() => {
    const last = study.periods[0]; // 최근 봉의 plot 값들 (plot 제목이 키)
    if (last) console.log(new Date(last.$time * 1000).toISOString(), last);
  });

  process.on('SIGINT', () => {
    client.end();
    process.exit(0);
  });
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
