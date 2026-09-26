"""구름 = 타임프레임별 일목균형표(선행스팬 A/B, 변위) 가설 검증"""
import sys, glob, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
fs = sorted(glob.glob("../tv-api/reports/study_ULT_SQ_BYBIT_BTCUSDT_P_5m_*.csv"))
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open","high","low","close"): df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50)
df["dt"] = pd.to_datetime(df.time, unit="s", utc=True); df = df.set_index("dt"); c = df.close
def mid(s_h, s_l, n): return (s_h.rolling(n).max() + s_l.rolling(n).min()) / 2
for k, tf in [(2, "5min"), (3, "15min"), (4, "60min"), (5, "240min")]:
    a, b = num(f"_{k}_"), num(f"_{k}__2"); hi, lo = pd.concat([a, b], axis=1).max(axis=1), pd.concat([a, b], axis=1).min(axis=1)
    r = df[["open","high","low","close"]].resample(tf, label="left", closed="left").agg({"open":"first","high":"max","low":"min","close":"last"})
    print(f"\n══ 구름 {k} ({tf}) ══"); res = []
    for (t, kj, sb) in [(9, 26, 52), (7, 22, 44), (10, 30, 60), (20, 60, 120), (5, 13, 26), (9, 26, 52)]:
        ten, kij = mid(r.high, r.low, t), mid(r.high, r.low, kj)
        A, B = (ten + kij) / 2, mid(r.high, r.low, sb)
        for disp in (0, kj - 1, kj, 26):
            for sh in (0, 1):
                HA = A.shift(disp + sh).reindex(df.index, method="ffill"); HB = B.shift(disp + sh).reindex(df.index, method="ffill")
                top, bot = pd.concat([HA, HB], axis=1).max(axis=1), pd.concat([HA, HB], axis=1).min(axis=1)
                m = hi.notna() & top.notna()
                e = ((hi - top).abs() + (lo - bot).abs())[m] / c[m] * 100
                res.append((e.median(), e.mean(), f"일목({t},{kj},{sb}) 변위{disp} shift{sh}"))
        # 기준선/전환선 채널
        for disp in (0, 26):
            T = ten.shift(disp).reindex(df.index, method="ffill"); K = kij.shift(disp).reindex(df.index, method="ffill")
            top, bot = pd.concat([T, K], axis=1).max(axis=1), pd.concat([T, K], axis=1).min(axis=1)
            m = hi.notna() & top.notna(); e = ((hi - top).abs() + (lo - bot).abs())[m] / c[m] * 100
            res.append((e.median(), e.mean(), f"전환/기준({t},{kj}) 변위{disp}"))
    res = sorted(set(res))
    for e_med, e_mean, name in res[:6]:
        print(f"  {name:<34} |오차| 중앙값 {e_med:.4f}%  평균 {e_mean:.4f}%")
