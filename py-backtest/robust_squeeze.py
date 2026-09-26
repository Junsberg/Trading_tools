"""일수축 돌파 견고성: 파라미터 이웃, 전/후반, 롱/숏, 대조군 10회, 월별 (사용: python robust_squeeze.py [csv])"""
import sys, numpy as np, pandas as pd
from rule_backtest import backtest, stats, summary, by_period, random_baseline
sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1] if len(sys.argv) > 1 else "data/BTCUSDT_5m_1y.csv"
df = pd.read_csv(path); c, h, l = df.close, df.high, df.low; D = 288
print("데이터:", path, len(df), "봉")
def rule(ratio=0.6, avg_days=5, win=D):
    rh, rl = h.rolling(win).max(), l.rolling(win).min(); rng = rh - rl
    contr = rng.shift(1) < ratio * rng.rolling(avg_days * D).mean().shift(1)
    return (contr & (c > rh.shift(1))).astype(int) - (contr & (c < rl.shift(1))).astype(int)
LIM = dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3)
print("\n── 파라미터 이웃 (지정가, 2.0/4.0/576) ──")
print(f"{'ratio':>5} {'avgD':>4} {'win':>4} | {'n':>4} {'승률':>5} {'PF':>5} {'평균%':>7} {'누적%':>7} {'MDD':>6}")
for ratio in (0.5, 0.6, 0.7, 0.8):
    for avg_days in (3, 5, 10):
        for win in (D // 2, D):
            s = stats(backtest(df, rule(ratio, avg_days, win), sl_pct=2.0, tp_pct=4.0, max_hold=576, **LIM))
            print(f"{ratio:>5} {avg_days:>4} {win:>4} | {s['n']:>4} {s['win']:>5.1f} {s['pf']:>5.2f} {s['avg']:>+7.3f} {s['cum']:>+7.1f} {s['mdd']:>6.1f}")
print("\n── 청산 이웃 (기본 규칙, 지정가) ──")
e = rule()
for sl, tp, hold in [(1.0, 2.0, 288), (1.5, 3.0, 576), (2.0, 4.0, 576), (2.0, 6.0, 864), (2.5, 5.0, 864), (3.0, 6.0, 1152), (2.0, 0, 576), (2.0, 4.0, 288)]:
    s = stats(backtest(df, e, sl_pct=sl, tp_pct=tp, max_hold=hold, **LIM))
    print(f"  {sl}/{tp}/{hold:<5} n={s['n']:<4} 승률 {s['win']:5.1f}  PF {s['pf']:4.2f}  평균 {s['avg']:+.3f}%  누적 {s['cum']:+6.1f}%  MDD {s['mdd']:6.1f}%")
print("\n── 기본 규칙 (지정가 2.0/4.0/576) 분해 ──")
kw = dict(sl_pct=2.0, tp_pct=4.0, max_hold=576, **LIM)
tr = backtest(df, e, **kw); mid = df.time.iloc[len(df) // 2]
print(summary(tr, "전체")); print(summary(tr[tr.entry_time < mid], "전반")); print(summary(tr[tr.entry_time >= mid], "후반"))
print(summary(tr[tr.dir > 0], "롱만")); print(summary(tr[tr.dir < 0], "숏만"))
b = random_baseline(df, e, seeds=10, **kw); print(f"무작위 10회: PF 평균 {b['pf_mean']:.2f} 최고 {b['pf_max']:.2f}")
print("\n월별:"); print(by_period(tr, "M").to_string())
print("\n청산 사유별 평균:"); print(tr.groupby("reason").ret_pct.agg(["size", "mean"]).round(3).to_string())
