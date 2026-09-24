// 로그인 없이 BTCUSDT.P 1분봉 실시간 캔들 수신
require('dotenv').config();
const TradingView = require('@mathieuc/tradingview');

const SYMBOL = process.env.SYMBOL || 'BINANCE:BTCUSDT.P';
const TIMEFRAME = process.env.TIMEFRAME || '1';

const client = new TradingView.Client();
const chart = new client.Session.Chart();

chart.setMarket(SYMBOL, { timeframe: TIMEFRAME, range: 100 });

chart.onError((...err) => console.error('Chart error:', ...err));

chart.onSymbolLoaded(() => {
  console.log(`[${chart.infos.description}] ${TIMEFRAME}분봉 로드 완료`);
});

chart.onUpdate(() => {
  const bar = chart.periods[0]; // 가장 최근 봉
  if (!bar) return;
  const time = new Date(bar.time * 1000).toISOString();
  console.log(`${time} O:${bar.open} H:${bar.max} L:${bar.min} C:${bar.close} V:${bar.volume}`);
});

process.on('SIGINT', () => {
  client.end();
  process.exit(0);
});
