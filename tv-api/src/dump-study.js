// 지표(내 스크립트 / 초대 전용 / 공개)의 plot 값을 과거 구간째 덤프
//
// 트레이딩뷰가 계산한 지표 값을 봉 단위로 받아 JSON + CSV 로 저장한다.
// 파이썬 엔진(py-backtest)에서 신호 품질 분석·백테스트의 입력으로 쓴다.
//
// 사용:
//   npm run dump -- --id "PUB;1458539e..." --symbol BYBIT:BTCUSDT.P --range 5000
//   npm run dump -- --name "My Scalping Indicator"                    # 내 계정 스크립트 이름으로
//   npm run dump -- --id "PUB;..." --to 2026-09-01 --range 5000        # 리플레이로 과거 기준일 지정
//   npm run dump -- --id "PUB;..." --set "헥사곤 레벨 방식=수동"       # 입력값 변경
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const TradingView = require('./tv');

const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] !== undefined ? args[i + 1] : def;
};
const { SESSION, SIGNATURE } = process.env;
const SYMBOL = opt('symbol', process.env.SYMBOL || 'BINANCE:BTCUSDT.P');
const TIMEFRAME = opt('tf', process.env.TIMEFRAME || '5');
const RANGE = Number(opt('range', process.env.RANGE || 5000));
const ID = opt('id', null);
const NAME = opt('name', null);
const TO = opt('to', null);
const OUT = opt('out', null);
const toTs = TO ? (Number.isFinite(Number(TO)) ? Number(TO) : Math.floor(new Date(TO).getTime() / 1000)) : undefined;
const SETS = args.reduce((acc, a, i) => (a === '--set' && args[i + 1] ? [...acc, args[i + 1]] : acc), []);
const SETTLE_MS = 4000;
const TIMEOUT_MS = 120000;

if (!ID && !NAME) {
  console.error('--id <pineId> 또는 --name <내 스크립트 이름> 이 필요합니다');
  process.exit(1);
}
if (!SESSION || !SIGNATURE) {
  console.error('.env 에 SESSION, SIGNATURE 가 필요합니다 (익명 세션은 지표를 로드할 수 없음)');
  process.exit(1);
}

(async () => {
  let indicator;
  if (ID) {
    indicator = await TradingView.getIndicator(ID, 'last', SESSION, SIGNATURE);
  } else {
    const list = await TradingView.getPrivateIndicators(SESSION, SIGNATURE);
    const found = list.find((i) => i.name === NAME);
    if (!found) {
      console.error(`"${NAME}" 을 찾지 못했습니다. 내 스크립트:`);
      list.forEach((i) => console.error(' -', i.name));
      process.exit(1);
    }
    indicator = await found.get();
  }

  // 입력값 변경 (backtest.js 와 동일 규칙: 이름 정확 → in_N → 이름 일부)
  const inputs = indicator.inputs || {};
  const overrides = {};
  for (const s of SETS) {
    const eq = s.indexOf('=');
    const label = s.slice(0, eq).trim();
    const raw = s.slice(eq + 1).trim();
    const ids = Object.keys(inputs).filter((k) => !inputs[k].isHidden);
    const id = ids.find((k) => k === label || inputs[k].name === label)
      || ids.find((k) => String(inputs[k].name).toLowerCase().includes(label.toLowerCase()));
    if (!id) { console.error(`입력값 "${label}" 없음`); process.exit(1); }
    const t = inputs[id].type;
    const value = t === 'bool' ? /^(true|1|on|yes)$/i.test(raw) : (t === 'integer' || t === 'float') ? Number(raw) : raw;
    indicator.setOption(id, value);
    overrides[inputs[id].name] = value;
  }

  console.log(`지표: ${indicator.description}  |  ${SYMBOL} ${TIMEFRAME}분봉  |  ${RANGE}봉${TO ? `  |  기준 ${TO}` : ''}`);
  if (SETS.length) console.log('입력값 변경:', JSON.stringify(overrides));

  const client = new TradingView.Client({ token: SESSION, signature: SIGNATURE });
  const chart = new client.Session.Chart();
  chart.onError((...e) => console.error('Chart error:', ...e));
  chart.setMarket(SYMBOL, { timeframe: TIMEFRAME, range: RANGE, ...(toTs ? { replay: toTs } : {}) });
  const study = new chart.Study(indicator);
  study.onError((...e) => console.error('Study error:', ...e));

  let settle = null;
  const finish = () => {
    clearTimeout(killer);
    const bars = {};
    chart.periods.forEach((b) => { bars[b.time] = b; });
    const rows = study.periods.map((p) => {
      const b = bars[p.$time] || {};
      return { time: p.$time, open: b.open, high: b.max, low: b.min, close: b.close, volume: b.volume, ...p };
    }).sort((a, b) => a.time - b.time);
    rows.forEach((r) => { delete r.$time; });

    const dir = path.join(__dirname, '..', 'reports');
    fs.mkdirSync(dir, { recursive: true });
    const safe = (indicator.description || 'study').replace(/[^\w가-힣]+/g, '_');
    const sym = SYMBOL.replace(/[^\w]+/g, '_');
    const base = OUT || path.join(dir, `study_${safe}_${sym}_${TIMEFRAME}m_${TO || 'latest'}`);
    const cols = Object.keys(rows[0] || {});
    fs.writeFileSync(`${base}.json`, JSON.stringify({
      indicator: indicator.description, pineId: indicator.pineId, symbol: SYMBOL, timeframe: TIMEFRAME,
      range: RANGE, to: TO || null, inputs: overrides, plots: indicator.plots, columns: cols, rows,
    }));
    const csv = [cols.join(',')].concat(rows.map((r) => cols.map((c) => {
      const v = r[c];
      return v === undefined || v === null || v === 1e100 ? '' : v;
    }).join(','))).join('\n');
    fs.writeFileSync(`${base}.csv`, csv);

    const first = rows[0]; const last = rows[rows.length - 1];
    const ts = (t) => new Date(t * 1000).toISOString().replace('T', ' ').slice(0, 16);
    console.log(`봉 수: ${rows.length}  기간: ${first ? ts(first.time) : '-'} ~ ${last ? ts(last.time) : '-'}`);
    console.log(`열: ${cols.length}개`);
    console.log(`저장: ${path.relative(process.cwd(), base)}.json / .csv`);
    client.end();
    process.exit(0);
  };

  study.onUpdate(() => {
    clearTimeout(settle);
    settle = setTimeout(finish, SETTLE_MS);
  });
  const killer = setTimeout(() => {
    console.error(`${TIMEOUT_MS / 1000}초 내에 데이터를 받지 못했습니다 (periods=${study.periods.length})`);
    process.exit(1);
  }, TIMEOUT_MS);
})().catch((err) => { console.error(err); process.exit(1); });
