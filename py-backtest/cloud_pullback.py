"""가설: 구름 눌림목 — 상위 구름(15분/1시간) 위에서 5분 구름을 터치 후 위로 닫으면 롱, 반대면 숏 (ATH Ultimate 덤프 사용)"""
import glob, sys
import pandas as pd
from rule_backtest import backtest, summary, by_period
sys.stdout.reconfigure(encoding="utf-8")

fs = sorted(glob.glob("../tv-api/reports/study_ATH_Ultimate_V6_0_BYBIT_BTCUSDT_P_5m_*.csv"))
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open", "high", "low", "close"):
    df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
def band(k):  # 구름 k 상단/하단 (열 이름: _k_ / _k__2)
    a = pd.to_numeric(df[f"_{k}_"], errors="coerce"); b = pd.to_numeric(df[f"_{k}__2"], errors="coerce")
    a = a.where(a.abs() < 1e50); b = b.where(b.abs() < 1e50)
    return pd.concat([a, b], axis=1).max(axis=1), pd.concat([a, b], axis=1).min(axis=1)
hi = {}; lo = {}
for k in (1, 2, 3, 4, 5):
    hi[k], lo[k] = band(k)
c, h, l = df["close"], df["high"], df["low"]
print(f"봉 {len(df)}  {pd.to_datetime(df.time.iloc[0], unit='s'):%m-%d} ~ {pd.to_datetime(df.time.iloc[-1], unit='s'):%m-%d}\n")

def rule(touch, trend_ks):
    up = pd.Series(True, index=df.index); dn = pd.Series(True, index=df.index)
    for k in trend_ks:
        up &= c > hi[k]; dn &= c < lo[k]
    # 눌림목: 이번 봉 저가가 터치구름 상단 이하로 들어왔다가 종가는 상단 위 (롱) / 반대 (숏)
    longs = up & (l <= hi[touch]) & (c > hi[touch]) & (c.shift(1) > hi[touch].shift(1))
    shorts = dn & (h >= lo[touch]) & (c < lo[touch]) & (c.shift(1) < lo[touch].shift(1))
    return longs.astype(int) - shorts.astype(int)

for touch, trend in [(2, [3]), (2, [3, 4]), (2, [4]), (1, [3, 4]), (2, [3, 4, 5]), (3, [4, 5])]:
    e = rule(touch, trend)
    for sl, tp, hold in [(0.4, 0.8, 24), (0.5, 1.0, 36), (0.3, 0.9, 36), (0.6, 0.6, 24)]:
        tr = backtest(df, e, sl_pct=sl, tp_pct=tp, max_hold=hold)
        print(summary(tr, f"터치{touch} 추세{trend} {sl}/{tp}/{hold}"))
    print()

# 가장 기본형의 롱/숏·주별 분해
e = rule(2, [3, 4]); tr = backtest(df, e, sl_pct=0.5, tp_pct=1.0, max_hold=36)
print("롱만 :", summary(tr[tr.dir > 0], ""))
print("숏만 :", summary(tr[tr.dir < 0], ""))
print(by_period(tr, "W").to_string())
