"""스윙형 스크리닝: 5분봉 진입 + 수 시간~하루 보유, 시장가 vs 지정가, 무작위 대조군 포함 (1년 데이터)

사용: python screen_swing.py [data/BTCUSDT_5m_1y.csv]
"""
import sys
import numpy as np
import pandas as pd
from rule_backtest import backtest, stats, random_baseline, by_period

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1] if len(sys.argv) > 1 else "data/BTCUSDT_5m_1y.csv"
df = pd.read_csv(path)
dt = pd.to_datetime(df.time, unit="s", utc=True); kst = (dt.dt.hour + 9) % 24
c, h, l, v = df.close, df.high, df.low, df.volume
us = kst.isin([22, 23, 0, 1])
ema = lambda n: c.ewm(span=n, adjust=False).mean()
D = 288  # 하루 봉 수

rules = {}
# 1) 돌파 페이드
for N in (20, 40):
    hh = c > h.rolling(N).max().shift(1); ll = c < l.rolling(N).min().shift(1)
    rules[f"페이드{N}"] = ll.astype(int) - hh.astype(int)
    rules[f"페이드{N}+미국장"] = (ll & us).astype(int) - (hh & us).astype(int)
# 2) 상위 추세 + 5분 눌림목 (EMA20 터치 후 회복)
e20 = ema(20)
for name, up, dn in [("4h", c > ema(48 * 12), c < ema(48 * 12)), ("1d", c > ema(D), c < ema(D)),
                     ("4h&1d", (c > ema(48 * 12)) & (ema(48 * 12) > ema(D)), (c < ema(48 * 12)) & (ema(48 * 12) < ema(D)))]:
    pbL = up & (l <= e20) & (c > e20) & (c.shift(1) > e20.shift(1)); pbS = dn & (h >= e20) & (c < e20) & (c.shift(1) < e20.shift(1))
    rules[f"눌림목 EMA{name}"] = pbL.astype(int) - pbS.astype(int)
# 3) 24h 범위 극단 + 반전봉
rh, rl = h.rolling(D).max(), l.rolling(D).min(); pos = (c - rl) / (rh - rl)
revUp = (c > df.open) & (c > c.shift(1)); revDn = (c < df.open) & (c < c.shift(1))
rules["24h범위 하단반전"] = ((pos < 0.1) & revUp).astype(int) - ((pos > 0.9) & revDn).astype(int)
rules["24h범위 하단반전+미국장"] = ((pos < 0.1) & revUp & us).astype(int) - ((pos > 0.9) & revDn & us).astype(int)
# 4) 일간 VWAP 밴드 복귀
day = dt.dt.floor("D")
pv = (df.quote_volume).groupby(day).cumsum(); vv = v.groupby(day).cumsum(); vwap = pv / vv
dev = (c - vwap).rolling(50).std(); up_b, lo_b = vwap + 2 * dev, vwap - 2 * dev
rules["VWAP 2σ 복귀"] = ((c.shift(1) < lo_b.shift(1)) & (c > lo_b)).astype(int) - ((c.shift(1) > up_b.shift(1)) & (c < up_b)).astype(int)
# 5) 주문흐름 괴리 (12봉 가격 vs 12봉 테이커 불균형)
imb = ((2 * df.taker_buy_base - v) / v).rolling(12).mean(); zf = (imb - imb.rolling(D).mean()) / imb.rolling(D).std()
pr = c.pct_change(12)
rules["흐름괴리"] = ((pr < pr.rolling(D).quantile(0.2)) & (zf > 1)).astype(int) - ((pr > pr.rolling(D).quantile(0.8)) & (zf < -1)).astype(int)
# 6) 일간 범위 수축 후 24h 고저 돌파 (추세 추종, 큰 목표용)
rng24 = (rh - rl); contr = rng24.shift(1) < 0.6 * rng24.rolling(5 * D).mean().shift(1)
rules["일수축 돌파"] = (contr & (c > rh.shift(1))).astype(int) - (contr & (c < rl.shift(1))).astype(int)
# 7) 일수축 돌파 페이드
rules["일수축 돌파 페이드"] = -rules["일수축 돌파"]

exits = [(1.0, 2.0, 144), (1.0, 3.0, 288), (1.5, 3.0, 288), (1.5, 4.5, 576), (2.0, 4.0, 576)]
modes = [("시장가", dict(entry_mode="market")), ("지정가", dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3))]

rows = []
for name, e in rules.items():
    e = e.fillna(0).astype(int)
    for sl, tp, hold in exits:
        for mname, mkw in modes:
            kw = dict(sl_pct=sl, tp_pct=tp, max_hold=hold, **mkw)
            tr = backtest(df, e, **kw)
            if len(tr) < 40:
                continue
            s = stats(tr); base = random_baseline(df, e, seeds=3, **kw)
            months = by_period(tr, "M"); pos_m = int((months["sum"] > 0).sum())
            rows.append({"규칙": name, "청산": f"{sl}/{tp}/{hold}", "진입": mname, "n": s["n"], "승률": s["win"], "PF": s["pf"],
                         "평균%": s["avg"], "누적%": s["cum"], "MDD": s["mdd"], "흑자월": f"{pos_m}/{len(months)}",
                         "무작위PF": base["pf_mean"], "무작위max": base["pf_max"], "초과": s["pf"] - base["pf_max"]})
            print(f"  {name:<18} {sl}/{tp}/{hold:<4} {mname} n={s['n']:<4} PF {s['pf']:.2f} (무작위 {base['pf_mean']:.2f}/{base['pf_max']:.2f}) 누적 {s['cum']:+.1f}%", flush=True)

res = pd.DataFrame(rows)
res["점수"] = res["초과"]  # 무작위 최고치보다 얼마나 나은가
pd.set_option("display.width", 250)
print("\n══ 상위 25 (무작위 대조군 최고치 대비 초과 손익비 순) ══")
print(res.sort_values("점수", ascending=False).head(25).round(3).to_string(index=False))
print(f"\n전체 {len(res)}개 | PF>1: {(res.PF > 1).sum()} | PF>1 이면서 무작위max 초과: {((res.PF > 1) & (res.초과 > 0)).sum()} | 초과>0.15: {(res.초과 > 0.15).sum()}")
res.to_csv("reports_screen_swing.csv", index=False)
