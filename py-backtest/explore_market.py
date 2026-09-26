"""바이낸스 5분봉 지형 탐색: 시간대 효과, 자기상관, 큰 봉 이후 행동 (규칙 설계 전 단계)"""
import sys, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
df = pd.read_csv("data/BTCUSDT_5m.csv"); df["dt"] = pd.to_datetime(df.time, unit="s", utc=True)
r = df.close.pct_change() * 100
df["r"] = r; df["hour"] = df.dt.dt.hour; df["kst"] = (df.dt.dt.hour + 9) % 24
print(f"봉 {len(df):,}  {df.dt.iloc[0]:%Y-%m-%d} ~ {df.dt.iloc[-1]:%Y-%m-%d}   5분 수익률 표준편차 {r.std():.3f}%  |수익률| 평균 {r.abs().mean():.3f}%  (왕복 수수료 0.08%)\n")

print("── 시간대(KST)별: 평균 수익률(bp), |수익률| 평균(%), 거래량 비율 ──")
g = df.groupby("kst")
tab = pd.DataFrame({"avg_bp": (g.r.mean() * 100).round(2), "abs%": g.r.apply(lambda s: s.abs().mean()).round(3), "vol": (g.volume.mean() / df.volume.mean()).round(2)})
print(tab.T.to_string())

print("\n── 자기상관: 직전 k봉 수익률 부호 → 다음 봉 수익률 (양수=추세 지속, 음수=되돌림) ──")
for k in (1, 3, 6, 12, 24):
    past = df.close.pct_change(k).shift(1); nxt = df.close.pct_change(1)
    m = past.notna() & nxt.notna()
    corr = np.corrcoef(past[m], nxt[m])[0, 1]
    up = nxt[m & (past > 0)].mean() * 100; dn = nxt[m & (past < 0)].mean() * 100
    print(f"  k={k:<3} 상관 {corr:+.4f}   상승 후 다음봉 {up:+.3f}bp   하락 후 다음봉 {dn:+.3f}bp")

print("\n── 큰 봉(|수익률| 상위 5%) 이후 N봉 누적 수익률 (봉 방향 기준, +면 추세 지속) ──")
thr = r.abs().quantile(0.95); big = r.abs() > thr
sign = np.sign(r)
for N in (1, 3, 6, 12, 24):
    fwd = (df.close.shift(-N) / df.close - 1) * 100 * sign
    x = fwd[big].dropna()
    print(f"  N={N:<3} n={len(x)}  평균 {x.mean():+.3f}%  지속확률 {(x > 0).mean() * 100:.0f}%")

print("\n── 큰 거래량 봉(상위 5%) 이후 N봉 (봉 방향 기준) ──")
bigv = df.volume > df.volume.quantile(0.95)
for N in (1, 3, 6, 12, 24):
    fwd = (df.close.shift(-N) / df.close - 1) * 100 * sign
    x = fwd[bigv].dropna()
    print(f"  N={N:<3} n={len(x)}  평균 {x.mean():+.3f}%  지속확률 {(x > 0).mean() * 100:.0f}%")

print("\n── 20봉 고점/저점 돌파 종가 이후 N봉 (돌파 방향 기준) ──")
hh = df.close > df.high.rolling(20).max().shift(1); ll = df.close < df.low.rolling(20).min().shift(1)
for N in (3, 6, 12, 24, 48):
    fu = (df.close.shift(-N) / df.close - 1) * 100; fd = -(df.close.shift(-N) / df.close - 1) * 100
    xu, xd = fu[hh].dropna(), fd[ll].dropna()
    print(f"  N={N:<3} 상향돌파 n={len(xu)} 평균 {xu.mean():+.3f}% 지속 {(xu > 0).mean() * 100:.0f}%   하향돌파 n={len(xd)} 평균 {xd.mean():+.3f}% 지속 {(xd > 0).mean() * 100:.0f}%")

print("\n── 월별 변동성/추세 (참고: 어느 달이 어떤 장이었나) ──")
m = df.set_index("dt").resample("ME").agg(close=("close", "last"), first=("close", "first"), absr=("r", lambda s: s.abs().mean()))
m["ret%"] = (m.close / m["first"] - 1) * 100
print(m[["ret%", "absr"]].round(3).to_string())
