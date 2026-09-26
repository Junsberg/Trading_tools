"""주문 흐름(테이커 매수 비율) 1차 점검: 극단값 이후 수익률, 간단 규칙"""
import sys, numpy as np, pandas as pd
from rule_backtest import backtest, summary, by_period
sys.stdout.reconfigure(encoding="utf-8")
df = pd.read_csv("data/BTCUSDT_5m_1y.csv"); dt = pd.to_datetime(df.time, unit="s", utc=True); kst = (dt.dt.hour + 9) % 24
c = df.close; v = df.volume; tb = df.taker_buy_base
ratio = (tb / v).replace([np.inf, -np.inf], np.nan)             # 0.5 = 균형, >0.5 매수 우위
imb = (2 * tb - v) / v                                             # -1..+1
for W in (1, 6, 12, 24):
    s = imb.rolling(W).mean(); z = (s - s.rolling(288).mean()) / s.rolling(288).std()
    print(f"── 누적 {W}봉 불균형 z (하루 기준) → 이후 수익률 ──")
    for N in (6, 24, 48):
        f = (c.shift(-N) / c - 1) * 100
        hiq, loq = z > 2, z < -2
        print(f"  N={N:<3} 강한매수(z>2) n={hiq.sum():<5} {f[hiq].mean():+.3f}%   강한매도(z<-2) n={loq.sum():<5} {f[loq].mean():+.3f}%   전체 {f.mean():+.3f}%")
# 가격과 흐름의 괴리: 가격은 내렸는데 매수 우위 (흡수) / 가격 올랐는데 매도 우위
print("\n── 괴리: 12봉 가격변화 vs 12봉 불균형 ──")
pr = c.pct_change(12) * 100; fl = imb.rolling(12).mean(); zf = (fl - fl.rolling(288).mean()) / fl.rolling(288).std()
absorbL = (pr < pr.rolling(288).quantile(0.2)) & (zf > 1); absorbS = (pr > pr.rolling(288).quantile(0.8)) & (zf < -1)
for N in (12, 24, 48, 96):
    f = (c.shift(-N) / c - 1) * 100
    print(f"  N={N:<3} 하락+매수우위 n={absorbL.sum():<5} {f[absorbL].mean():+.3f}%   상승+매도우위 n={absorbS.sum():<5} {-f[absorbS].mean():+.3f}%(숏기준)   전체 {f.mean():+.3f}%")
print("\n── 규칙 백테스트 (메이커 0.02): 괴리 신호, 재진입은 청산 후 ──")
e = absorbL.astype(int) - absorbS.astype(int)
us = kst.isin([22, 23, 0, 1])
for label, ee in [("전체시간", e), ("미국장", e.where(us, 0))]:
    for sl, tp, hold in [(0.5, 1.0, 24), (0.8, 1.6, 48), (1.0, 3.0, 144)]:
        tr = backtest(df, ee, sl_pct=sl, tp_pct=tp, max_hold=hold, fee_pct=0.02)
        print(summary(tr, f"{label} {sl}/{tp}/{hold}"))
tr = backtest(df, e, sl_pct=0.8, tp_pct=1.6, max_hold=48, fee_pct=0.02)
print("\n롱만:", summary(tr[tr.dir > 0])); print("숏만:", summary(tr[tr.dir < 0]))
print(by_period(tr, "M").to_string())
