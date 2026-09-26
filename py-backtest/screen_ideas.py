"""아이디어 가족 1차 스크리닝 (바이낸스 180일): 돌파 페이드 / 시간대 / 상위추세+눌림목"""
import sys, itertools, numpy as np, pandas as pd
from rule_backtest import backtest, summary, by_period
sys.stdout.reconfigure(encoding="utf-8")
df = pd.read_csv("data/BTCUSDT_5m.csv"); dt = pd.to_datetime(df.time, unit="s", utc=True); kst = (dt.dt.hour + 9) % 24
c, h, l, v = df.close, df.high, df.low, df.volume
ema = lambda n: c.ewm(span=n, adjust=False).mean()
atr = (pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)).rolling(14).mean()
us = (kst >= 22) | (kst <= 1)

rules = {}
# 1) 돌파 페이드: N봉 고점 상향돌파 종가 → 숏, 저점 하향돌파 → 롱 (가짜 돌파 역이용)
for N in (20, 40):
    hh = c > h.rolling(N).max().shift(1); ll = c < l.rolling(N).min().shift(1)
    rules[f"페이드{N}"] = ll.astype(int) - hh.astype(int)
    rules[f"페이드{N}+미국장"] = (ll & us).astype(int) - (hh & us).astype(int)
# 1b) 돌파 실패 확인형: 돌파 다음 봉이 돌파 레벨 안으로 다시 닫힘
for N in (20,):
    lvlH = h.rolling(N).max().shift(1); lvlL = l.rolling(N).min().shift(1)
    failH = (c.shift(1) > lvlH.shift(1)) & (c < lvlH.shift(1)); failL = (c.shift(1) < lvlL.shift(1)) & (c > lvlL.shift(1))
    rules[f"돌파실패{N}"] = failL.astype(int) - failH.astype(int)
    rules[f"돌파실패{N}+미국장"] = (failL & us).astype(int) - (failH & us).astype(int)
# 2) 시간대: 미국장 시작(KST 22시 첫 봉) 방향 추종 / 역추종
first = (kst == 22) & (kst.shift(1) != 22)
mom = np.sign(c - c.shift(6))
rules["22시 6봉모멘텀 추종"] = (first * mom).fillna(0).astype(int)
rules["22시 6봉모멘텀 역"] = (-(first * mom)).fillna(0).astype(int)
# 3) 상위 추세(1h=12봉·4h=48봉 EMA) + 5분 눌림목(EMA20 터치 후 회복)
e20, e12h, e4h = ema(20), ema(12 * 12), ema(48 * 12)
for name, trendUp, trendDn in [("EMA1h", c > e12h, c < e12h), ("EMA4h", c > e4h, c < e4h), ("EMA1h&4h", (c > e12h) & (e12h > e4h), (c < e12h) & (e12h < e4h))]:
    pbL = trendUp & (l <= e20) & (c > e20) & (c.shift(1) > e20.shift(1)); pbS = trendDn & (h >= e20) & (c < e20) & (c.shift(1) < e20.shift(1))
    rules[f"눌림목 {name}"] = pbL.astype(int) - pbS.astype(int)
    rules[f"눌림목 {name}+미국장"] = (pbL & us).astype(int) - (pbS & us).astype(int)

exits = [(0.4, 0.8, 24), (0.6, 1.2, 48), (0.8, 2.0, 96), (1.0, 3.0, 144)]
rows = []
for name, e in rules.items():
    for sl, tp, hold in exits:
        for fee, tag in ((0.04, "T"), (0.02, "M")):
            tr = backtest(df, e, sl_pct=sl, tp_pct=tp, max_hold=hold, fee_pct=fee)
            if len(tr) < 30: continue
            r = tr.ret_pct; gp = r[r > 0].sum(); gl = -r[r < 0].sum(); pf = gp / gl if gl else 9.99
            months = by_period(tr, "M"); pos = int((months["sum"] > 0).sum()) if len(months) else 0
            rows.append((name, f"{sl}/{tp}/{hold}", tag, len(tr), (r > 0).mean() * 100, pf, r.mean(), (1 + r / 100).prod() * 100 - 100, pos, len(months)))
res = pd.DataFrame(rows, columns=["규칙", "청산", "수수료", "n", "승률", "PF", "평균%", "누적%", "흑자월", "월수"]).sort_values("PF", ascending=False)
pd.set_option("display.width", 200)
print("상위 20 (PF 순, T=테이커0.04 M=메이커0.02)\n", res.head(20).round(3).to_string(index=False))
print("\n테이커만 상위 10\n", res[res.수수료 == "T"].head(10).round(3).to_string(index=False))
print(f"\n전체 {len(res)}개 조합 중 PF>1: {(res.PF > 1).sum()}개, 테이커 PF>1: {((res.PF > 1) & (res.수수료 == 'T')).sum()}개")
