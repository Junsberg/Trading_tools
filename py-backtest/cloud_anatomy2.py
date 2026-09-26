"""구름 = 타임프레임별 고가/저가 이동평균 채널 가설 검증 + 중심선 지연 측정"""
import sys, glob, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
fs = sorted(glob.glob("../tv-api/reports/study_ULT_SQ_BYBIT_BTCUSDT_P_5m_*.csv"))
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open","high","low","close"): df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50)
df["dt"] = pd.to_datetime(df.time, unit="s", utc=True); df = df.set_index("dt")
c = df.close
def wma(s, n): w = np.arange(1, n + 1); return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
def hma(s, n): return wma(2 * wma(s, max(n // 2, 1)) - wma(s, n), max(int(np.sqrt(n)), 1))
def rma(s, n): return s.ewm(alpha=1 / n, adjust=False).mean()
MAS = {"EMA": lambda s, n: s.ewm(span=n, adjust=False).mean(), "SMA": lambda s, n: s.rolling(n).mean(), "WMA": wma, "HMA": hma, "RMA": rma}
for k, tf in [(2, "5min"), (3, "15min"), (4, "60min"), (5, "240min")]:
    a, b = num(f"_{k}_"), num(f"_{k}__2"); hi, lo = pd.concat([a, b], axis=1).max(axis=1), pd.concat([a, b], axis=1).min(axis=1)
    r = df[["open","high","low","close"]].resample(tf, label="left", closed="left").agg({"open":"first","high":"max","low":"min","close":"last"})
    # 상위 TF 값은 그 봉이 확정된 뒤(다음 봉부터) 5분봉에 반영되는 게 보통 → 1봉 shift 도 같이 시험
    print(f"\n══ 구름 {k} ({tf}) ══")
    res = []
    for name, fn in MAS.items():
        for n in (3, 5, 7, 8, 9, 10, 12, 13, 14, 15, 20, 21, 24, 26, 30, 34, 40, 50):
            for sh in (0, 1):
                H = fn(r.high, n).shift(sh).reindex(df.index, method="ffill"); L = fn(r.low, n).shift(sh).reindex(df.index, method="ffill")
                m = hi.notna() & H.notna() & L.notna()
                e = ((hi - H).abs() + (lo - L).abs())[m] / c[m] * 100
                res.append((e.median(), e.mean(), name, n, sh))
    # 돈치안 중간/켈트너류도 시험: (highest+lowest)/2 ± ATR
    res.sort()
    for e_med, e_mean, name, n, sh in res[:8]:
        print(f"  상단≈{name}(high,{n:>2}) 하단≈{name}(low,{n:>2}) shift{sh}  |오차| 중앙값 {e_med:.4f}%  평균 {e_mean:.4f}%")
    mid = (hi + lo) / 2; m = mid.notna()
    lags = {L: np.corrcoef(mid[m].diff(1).dropna().iloc[L:], c[m].diff(1).dropna().iloc[:-L] if L else c[m].diff(1).dropna())[0, 1] for L in (0, 1, 2, 3, 5, 8, 13, 21)}
    print("  중심선 변화 vs 가격 변화 지연 상관:", {k2: round(v, 3) for k2, v in lags.items()})
