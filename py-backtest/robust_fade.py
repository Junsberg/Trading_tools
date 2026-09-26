"""돌파 페이드+미국장 가족 견고성: 파라미터 이웃, 전/후반 분할, 롱숏 분해"""
import sys, numpy as np, pandas as pd
from rule_backtest import backtest, summary, by_period
sys.stdout.reconfigure(encoding="utf-8")
df = pd.read_csv("data/BTCUSDT_5m.csv"); dt = pd.to_datetime(df.time, unit="s", utc=True); kst = (dt.dt.hour + 9) % 24
c, h, l = df.close, df.high, df.low
def fade(N, hours):
    us = kst.isin(hours)
    hh = (c > h.rolling(N).max().shift(1)) & us; ll = (c < l.rolling(N).min().shift(1)) & us
    return ll.astype(int) - hh.astype(int)
def pf(tr):
    r = tr.ret_pct; gl = -r[r < 0].sum(); return (r[r > 0].sum() / gl) if gl else 9.99
US = [22, 23, 0, 1]
print("── 파라미터 이웃 (메이커 0.02) ──")
print(f"{'N':>3} {'SL':>4} {'TP':>4} {'hold':>4} | {'n':>4} {'PF':>5} {'평균%':>7} {'누적%':>7}")
for N in (10, 15, 20, 30, 40):
    for sl, tp, hold in [(0.8, 2.4, 144), (1.0, 3.0, 144), (1.2, 3.6, 144), (1.0, 2.0, 144), (1.0, 3.0, 96), (1.0, 3.0, 192), (1.5, 4.5, 192)]:
        tr = backtest(df, fade(N, US), sl_pct=sl, tp_pct=tp, max_hold=hold, fee_pct=0.02)
        r = tr.ret_pct
        print(f"{N:>3} {sl:>4} {tp:>4} {hold:>4} | {len(tr):>4} {pf(tr):>5.2f} {r.mean():>+7.3f} {(1+r/100).prod()*100-100:>+7.1f}")
print("\n── 시간대 이웃 (N=20, 1.0/3.0/144, 메이커) ──")
for name, hours in [("22-01", [22, 23, 0, 1]), ("21-02", [21, 22, 23, 0, 1, 2]), ("22-23", [22, 23]), ("00-03", [0, 1, 2, 3]), ("전체시간", list(range(24))), ("아시아 09-16", list(range(9, 17))), ("유럽 16-21", list(range(16, 22)))]:
    tr = backtest(df, fade(20, hours), sl_pct=1.0, tp_pct=3.0, max_hold=144, fee_pct=0.02)
    print(summary(tr, name))
print("\n── 전/후반 분할 + 롱/숏 (N=20, 1.0/3.0/144, 메이커) ──")
e = fade(20, US); tr = backtest(df, e, sl_pct=1.0, tp_pct=3.0, max_hold=144, fee_pct=0.02)
mid = df.time.iloc[len(df) // 2]
print(summary(tr[tr.entry_time < mid], "전반 90일")); print(summary(tr[tr.entry_time >= mid], "후반 90일"))
print(summary(tr[tr.dir > 0], "롱만")); print(summary(tr[tr.dir < 0], "숏만"))
print("\n월별:"); print(by_period(tr, "M").to_string())
print("\n── 같은 규칙 테이커 0.04 ──"); print(summary(backtest(df, e, sl_pct=1.0, tp_pct=3.0, max_hold=144, fee_pct=0.04), "테이커"))
