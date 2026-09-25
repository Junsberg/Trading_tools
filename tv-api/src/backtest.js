// Pine strategy 백테스트 리포트 수신
//
// 트레이딩뷰 에센셜 등급은 UI에서 전략 테스터 날짜 지정이 안 되지만,
// API로는 "기준 시점(to)부터 과거로 N개 봉"을 로드해 그 구간의 리포트를 통째로 받을 수 있다.
//
// 사용:
//   npm run backtest                                  # .env 의 STRATEGY_NAME (내 계정 저장 전략, 로그인 필요)
//   npm run backtest -- --id "STD;MACD%1Strategy"     # 공개 전략 ID로 테스트 (로그인 불필요)
//   npm run backtest -- --to 2026-09-01 --range 5000  # 2026-09-01 까지의 5000봉
//   npm run backtest -- --tf 15                       # 타임프레임 변경
//   npm run backtest -- --list-inputs                 # 전략 입력값 목록만 출력
//   npm run backtest -- --set "손절 %=0.6" --set "익절 %=1.2"   # 입력값을 바꿔서 실행 (트레이딩뷰 저장 불필요)
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const TradingView = require('./tv'); // zlib 리포트 대응 래퍼

// ── 인자 파싱 ────────────────────────────────────────
const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] !== undefined ? args[i + 1] : def;
};

const { SESSION, SIGNATURE } = process.env;
const SYMBOL = opt('symbol', process.env.SYMBOL || 'BINANCE:BTCUSDT.P');
const TIMEFRAME = opt('tf', process.env.TIMEFRAME || '5');
const RANGE = Number(opt('range', process.env.RANGE || 5000));
const PUBLIC_ID = opt('id', null);
const STRATEGY_NAME = opt('name', process.env.STRATEGY_NAME || 'My Scalping Strategy');
const TO = opt('to', null); // YYYY-MM-DD 또는 unix 초
const LIST_INPUTS = args.includes('--list-inputs');
const SETS = args.reduce((acc, a, i) => (a === '--set' && args[i + 1] ? [...acc, args[i + 1]] : acc), []); // "이름=값" 목록
const toTs = TO ? (Number.isFinite(Number(TO)) ? Number(TO) : Math.floor(new Date(TO).getTime() / 1000)) : undefined;

const SETTLE_MS = 3000; // 마지막 리포트 패킷 후 이 시간 동안 조용하면 완료로 간주
const TIMEOUT_MS = 90000;

const fmt = (n, d = 2) => (typeof n === 'number' ? n.toFixed(d) : String(n));
const pct = (n, d = 2) => (typeof n === 'number' ? (n * 100).toFixed(d) + '%' : String(n)); // 리포트의 비율은 0~1 소수
const ts = (t) => {
  if (!t) return '-';
  const ms = t > 1e12 ? t : t * 1000; // 리포트 거래 시각은 ms, 차트 봉 시각은 초
  return new Date(ms).toISOString().replace('T', ' ').slice(0, 16);
};

(async () => {
  // ── 지표 로드 ──────────────────────────────────────
  let indicator;
  if (PUBLIC_ID) {
    indicator = await TradingView.getIndicator(PUBLIC_ID, 'last', SESSION || '', SIGNATURE || '');
  } else {
    if (!SESSION || !SIGNATURE) {
      console.error('.env 에 SESSION, SIGNATURE 를 설정하거나 --id <공개 전략 ID> 를 사용하세요');
      process.exit(1);
    }
    const list = await TradingView.getPrivateIndicators(SESSION, SIGNATURE);
    const found = list.find((i) => i.name === STRATEGY_NAME);
    if (!found) {
      console.error(`"${STRATEGY_NAME}" 을 찾지 못했습니다. 내 스크립트 목록:`);
      list.forEach((i) => console.error(' -', i.name));
      process.exit(1);
    }
    indicator = await found.get();
  }
  // 전략 리포트를 받으려면 스크립트 타입을 전략으로 지정해야 함 (라이브러리가 자동 판정하지 않음)
  indicator.setType('StrategyScript@tv-scripting-101!');

  // ── 입력값 목록 / 변경 ──────────────────────────────
  const inputs = indicator.inputs || {};
  // 이름 정확 일치 → in_N → 이름 일부 포함(대소문자 무시) 순으로 찾는다
  const findInput = (label) => {
    const ids = Object.keys(inputs).filter((id) => !inputs[id].isHidden);
    return ids.find((id) => id === label || inputs[id].name === label)
      || ids.find((id) => String(inputs[id].name).toLowerCase().includes(label.toLowerCase()));
  };
  if (LIST_INPUTS) {
    console.log(`\n"${indicator.description}" 입력값:`);
    Object.keys(inputs).forEach((id) => {
      const inp = inputs[id];
      if (inp.isHidden) return;
      console.log(`  ${id.padEnd(6)} ${String(inp.type).padEnd(10)} ${JSON.stringify(inp.value).padEnd(8)} ${inp.name}`);
    });
    process.exit(0);
  }
  const overrides = {};
  for (const s of SETS) {
    const eq = s.indexOf('=');
    const label = s.slice(0, eq).trim();
    const raw = s.slice(eq + 1).trim();
    const id = findInput(label);
    if (!id) {
      console.error(`입력값 "${label}" 을 찾지 못했습니다. --list-inputs 로 이름을 확인하세요.`);
      process.exit(1);
    }
    const t = inputs[id].type;
    const value = t === 'bool' ? /^(true|1|on|yes)$/i.test(raw)
      : (t === 'integer' || t === 'float') ? Number(raw)
        : raw;
    indicator.setOption(id, value);
    overrides[inputs[id].name] = value;
  }
  if (SETS.length) console.log('입력값 변경:', JSON.stringify(overrides));
  console.log(`전략: ${indicator.description}  |  ${SYMBOL} ${TIMEFRAME}분봉  |  ${RANGE}봉${TO ? `  |  기준 ${TO}` : ''}`);

  // ── 차트 + 전략 ────────────────────────────────────
  const client = new TradingView.Client(SESSION ? { token: SESSION, signature: SIGNATURE } : {});
  const chart = new client.Session.Chart();
  chart.onError((...e) => console.error('Chart error:', ...e));
  // 기준일 지정은 라이브러리의 `to`(bar_count 참조)가 현재 트레이딩뷰에서 무시되므로
  // 리플레이 세션으로 처리한다: 차트가 해당 시각까지의 봉만 갖고, 리포트도 그 시점까지 계산된다.
  chart.setMarket(SYMBOL, { timeframe: TIMEFRAME, range: RANGE, ...(toTs ? { replay: toTs } : {}) });

  const study = new chart.Study(indicator);
  study.onError((...e) => console.error('Strategy error:', ...e));

  let gotPerf = false;
  let gotTrades = false;
  let settle = null;

  const finish = () => {
    clearTimeout(killer);
    const r = study.strategyReport;
    const bars = chart.periods;
    const first = bars[bars.length - 1];
    const last = bars[0];
    const all = r.performance.all || {};

    console.log('\n── 구간 ────────────────────────────────');
    console.log(`  봉 수    : ${bars.length}`);
    console.log(`  기간     : ${ts(first && first.time)}  ~  ${ts(last && last.time)}`);

    console.log('── 성과 (전체) ─────────────────────────');
    console.log(`  순이익   : ${fmt(all.netProfit)}  (${pct(all.netProfitPercent)})`);
    console.log(`  거래 수  : ${all.totalTrades}  (승 ${all.numberOfWiningTrades} / 패 ${all.numberOfLosingTrades})`);
    console.log(`  승률     : ${pct(all.percentProfitable)}`);
    console.log(`  손익비   : ${fmt(all.profitFactor)}`);
    console.log(`  평균거래 : ${fmt(all.avgTrade)}  (${pct(all.avgTradePercent, 3)})`);
    console.log(`  수수료   : ${fmt(all.commissionPaid)}`);
    console.log(`  최대 DD  : ${fmt(r.performance.maxStrategyDrawDown)}  (${pct(r.performance.maxStrategyDrawDownPercent)})`);
    console.log(`  B&H 수익 : ${pct(r.performance.buyHoldReturnPercent)}`);
    console.log(`  샤프     : ${fmt(r.performance.sharpeRatio, 3)}`);

    console.log('── 최근 거래 5건 (오래된 순) ───────────');
    r.trades.slice(0, 5).reverse().forEach((t) => { // trades[0] 이 최신
      console.log(`  ${ts(t.entry.time)} ${t.entry.type.padEnd(5)} @${fmt(t.entry.value, 1)} → ${ts(t.exit.time)} @${fmt(t.exit.value, 1)}  ${pct(t.profit.p, 3)}`);
    });

    // ── JSON 저장 ────────────────────────────────────
    const dir = path.join(__dirname, '..', 'reports');
    fs.mkdirSync(dir, { recursive: true });
    const safe = indicator.description.replace(/[^\w가-힣]+/g, '_');
    const file = path.join(dir, `${safe}_${TIMEFRAME}m_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`);
    fs.writeFileSync(file, JSON.stringify({
      strategy: indicator.description,
      symbol: SYMBOL,
      timeframe: TIMEFRAME,
      range: RANGE,
      to: TO || null,
      inputs: overrides,
      bars: bars.length,
      from: first && first.time,
      until: last && last.time,
      performance: r.performance,
      settings: r.settings,
      trades: r.trades,
      history: r.history,
    }, null, 2));
    console.log(`\n저장: ${path.relative(process.cwd(), file)}`);
    // sweep.js 등 다른 스크립트가 파싱하는 한 줄 요약
    console.log('RESULT ' + JSON.stringify({
      to: TO || null,
      trades: all.totalTrades,
      winRate: all.percentProfitable,
      pf: all.profitFactor,
      netPct: all.netProfitPercent,
      avgTradePct: all.avgTradePercent,
      fee: all.commissionPaid,
      ddPct: r.performance.maxStrategyDrawDownPercent,
      file: path.relative(process.cwd(), file),
    }));

    client.end();
    process.exit(0);
  };

  study.onUpdate((changes = []) => {
    if (changes.includes('report.perf')) gotPerf = true;
    if (changes.includes('report.trades')) gotTrades = true;
    if (gotPerf && gotTrades) {
      clearTimeout(settle);
      settle = setTimeout(finish, SETTLE_MS);
    }
  });

  const killer = setTimeout(() => {
    console.error(`\n${TIMEOUT_MS / 1000}초 내에 리포트를 받지 못했습니다 (perf=${gotPerf}, trades=${gotTrades})`);
    client.end();
    process.exit(1);
  }, TIMEOUT_MS);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
