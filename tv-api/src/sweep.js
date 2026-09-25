// 입력값 조합 × 구간 스윕
//
// backtest.js 를 조합마다 순차 실행해 구간별 성과를 표로 비교한다.
// 트레이딩뷰에 저장하지 않고 --set 으로 입력값만 바꾸므로 로직 파라미터 탐색에 쓴다.
//
// 사용:
//   npm run sweep                                  # src/sweeps/default.json 의 조합
//   npm run sweep -- --file src/sweeps/exit.json   # 다른 조합 파일
//   npm run sweep -- --to 2026-09-01,2026-08-10    # 구간 지정 (비우면 최신, 쉼표 구분; "latest" = 최신)
//   npm run sweep -- --range 5000
//   npm run sweep -- --name "My Scalping Strategy B" --file src/sweeps/b.json   # 다른 전략
//
// 조합 파일 형식 (JSON 배열): [{ "label": "기본", "set": {} }, { "label": "넓은 손익", "set": { "손절": 0.8, "익절": 1.6 } }]
//   set 의 키는 backtest.js --set 과 동일 (입력값 이름 일부로 매칭)
require('dotenv').config();
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const opt = (name, def) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] !== undefined ? args[i + 1] : def;
};

const FILE = opt('file', path.join(__dirname, 'sweeps', 'default.json'));
const TOS = opt('to', 'latest,2026-09-01,2026-08-10').split(',').map((s) => s.trim()).filter(Boolean);
const RANGE = opt('range', process.env.RANGE || '5000');
const NAME = opt('name', null); // 전략 이름 (비우면 backtest.js 가 .env 의 STRATEGY_NAME 사용)
const NAME_ARGS = NAME ? ['--name', NAME] : [];

const combos = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const pct = (n) => (typeof n === 'number' ? (n * 100).toFixed(1) : '-');

console.log(`조합 ${combos.length}개 × 구간 ${TOS.length}개 (${RANGE}봉)  |  ${path.relative(process.cwd(), FILE)}\n`);

const rows = [];
for (const combo of combos) {
  const setArgs = Object.entries(combo.set || {}).flatMap(([k, v]) => ['--set', `${k}=${v}`]);
  const perWindow = [];
  for (const to of TOS) {
    const toArgs = to === 'latest' ? [] : ['--to', to];
    const res = spawnSync(process.execPath, [path.join(__dirname, 'backtest.js'), '--range', RANGE, ...NAME_ARGS, ...toArgs, ...setArgs], { encoding: 'utf8' });
    const line = (res.stdout || '').split('\n').find((l) => l.startsWith('RESULT '));
    if (!line) {
      console.error(`[${combo.label}] ${to}: 실패\n${(res.stderr || res.stdout || '').slice(-400)}`);
      perWindow.push(null);
      continue;
    }
    const r = JSON.parse(line.slice(7));
    perWindow.push(r);
    console.log(`  ${combo.label.padEnd(18)} ${to.padEnd(11)} n=${String(r.trades).padEnd(4)} win=${pct(r.winRate).padStart(5)}%  PF=${r.pf.toFixed(2)}  net=${pct(r.netPct).padStart(6)}%  avg=${(r.avgTradePct * 100).toFixed(3)}%  DD=${pct(r.ddPct)}%`);
  }
  const ok = perWindow.filter(Boolean);
  const sumNet = ok.reduce((s, r) => s + r.netPct, 0);
  const minPf = ok.length ? Math.min(...ok.map((r) => r.pf)) : 0;
  const positive = ok.filter((r) => r.netPct > 0).length;
  rows.push({ label: combo.label, set: combo.set, windows: perWindow, sumNet, minPf, positive });
  console.log(`  → ${combo.label}: 합계 ${pct(sumNet)}%  최소PF ${minPf.toFixed(2)}  흑자구간 ${positive}/${ok.length}\n`);
}

console.log('── 요약 (합계 순) ──────────────────────────');
rows.sort((a, b) => b.sumNet - a.sumNet).forEach((r) => {
  console.log(`  ${r.label.padEnd(18)} 합계 ${pct(r.sumNet).padStart(6)}%  최소PF ${r.minPf.toFixed(2)}  흑자 ${r.positive}/${r.windows.filter(Boolean).length}  ${JSON.stringify(r.set)}`);
});

const outDir = path.join(__dirname, '..', 'reports');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, `sweep_${path.basename(FILE, '.json')}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`);
fs.writeFileSync(out, JSON.stringify({ file: FILE, range: RANGE, tos: TOS, rows }, null, 2));
console.log(`\n저장: ${path.relative(process.cwd(), out)}`);
