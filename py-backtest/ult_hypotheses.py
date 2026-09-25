"""ATH Ultimate 사용자 규칙 검증: 신호×구름 배열(H1), 구름 0/1 반등(H2)"""
import glob, sys
import numpy as np, pandas as pd
from rule_backtest import backtest, summary, by_period
sys.stdout.reconfigure(encoding="utf-8")

fs = sorted(glob.glob("../tv-api/reports/study_ULT_SQ_BYBIT_BTCUSDT_P_5m_*.csv"))
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open", "high", "low", "close"):
    df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50)
hi, lo, mid = {}, {}, {}
for k in range(6):
    a, b = num(f"_{k}_"), num(f"_{k}__2")
    hi[k] = pd.concat([a, b], axis=1).max(axis=1); lo[k] = pd.concat([a, b], axis=1).min(axis=1); mid[k] = (hi[k] + lo[k]) / 2
c, h, l = df["close"], df["high"], df["low"]
print(f"봉 {len(df)}  {pd.to_datetime(df.time.iloc[0], unit='s'):%m-%d} ~ {pd.to_datetime(df.time.iloc[-1], unit='s'):%m-%d}")

# ── 신호 열 (0 아닌 봉 수) ──
sigcols = [x for x in df.columns if x not in ("time","open","high","low","close","volume") and not x.endswith("_colorer") and not x.startswith("_") or x.startswith("__")]
sigcols = [x for x in sigcols if x not in ("time","open","high","low","close","volume") and not x.endswith("_colorer") and x not in ("2_","2__2")]
ev = {x: (num(x).fillna(0) != 0) for x in sigcols}
ev = {x: v for x, v in ev.items() if v.sum() >= 3}
print("신호 열 건수:", {x: int(v.sum()) for x, v in ev.items()})

# ── 구름 배열 (mid 기준, 0<1<2<3<4<5 위→정배열, 아래→역배열) ──
def aligned(ks, up=True):
    ok = pd.Series(True, index=df.index)
    for a, b in zip(ks[:-1], ks[1:]):
        ok &= (mid[a] > mid[b]) if up else (mid[a] < mid[b])
    return ok
bull_full, bear_full = aligned([0,1,2,3,4,5], True), aligned([0,1,2,3,4,5], False)
bull_3, bear_3 = aligned([1,2,3], True), aligned([1,2,3], False)
bull_45, bear_45 = aligned([2,3,4,5], True), aligned([2,3,4,5], False)
print(f"정배열(전체) {bull_full.mean()*100:.0f}%  역배열(전체) {bear_full.mean()*100:.0f}%  |  정배열(1-3) {bull_3.mean()*100:.0f}%  역배열(1-3) {bear_3.mean()*100:.0f}%")

def fwd_stats(mask, d, hs=(12, 24, 48)):
    idx = df.index[mask]; out = [f"n={len(idx):<4}"]
    for H in hs:
        r = [(c[i+H]/c[i]-1)*d*100 for i in idx if i+H < len(df)]
        if r: out.append(f"{H}봉 {np.mean(r):+.3f}% 적중 {np.mean(np.array(r)>0)*100:.0f}%")
    return "  ".join(out)

print("\n── H1: 신호 × 배열 (방향은 열 이름 LONG/SHORT) ──")
for x, v in ev.items():
    d = -1 if "SHORT" in x.upper() else 1
    bull, bear = (bull_3, bear_3)
    with_ = v & (bull if d > 0 else bear); against = v & (bear if d > 0 else bull)
    print(f"{x:<11} 전체     {fwd_stats(v, d)}")
    print(f"{'':<11} 배열일치 {fwd_stats(with_, d)}")
    print(f"{'':<11} 배열반대 {fwd_stats(against, d)}")

print("\n── H2: 구름 0/1 반등 (배열 조건 + 터치 후 방향 유지 종가) ──")
def bounce(k, bull, bear, need_prev=True):
    longs = bull & (l <= hi[k]) & (c > hi[k]); shorts = bear & (h >= lo[k]) & (c < lo[k])
    if need_prev:
        longs &= c.shift(1) > hi[k].shift(1); shorts &= c.shift(1) < lo[k].shift(1)
    return longs.astype(int) - shorts.astype(int)
for label, bull, bear in [("전체배열", bull_full, bear_full), ("1-3배열", bull_3, bear_3), ("2-5배열", bull_45, bear_45)]:
    for k in (0, 1):
        e = bounce(k, bull, bear)
        for sl, tp, hold in [(0.4, 0.8, 24), (0.3, 0.6, 12), (0.5, 1.5, 48)]:
            print(summary(backtest(df, e, sl_pct=sl, tp_pct=tp, max_hold=hold), f"{label} 구름{k} {sl}/{tp}/{hold}"))
    print()
