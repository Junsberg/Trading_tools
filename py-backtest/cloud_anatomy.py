"""Ultimate 구름의 통계적 성질 파악: 중심선은 어떤 평균에 가까운가, 폭은 변동성에 어떻게 반응하는가"""
import sys, glob, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")
fs = sorted(glob.glob("../tv-api/reports/study_ULT_SQ_BYBIT_BTCUSDT_P_5m_*.csv"))
df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
for c in ("open","high","low","close"): df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50)
c, h, l = df.close, df.high, df.low
tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
def wma(s, n): w = np.arange(1, n + 1); return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
def hma(s, n): return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))
# 5분봉 차트에서 구름 k 의 타임프레임: 2=5m(1x), 3=15m(3x), 4=60m(12x), 5=240m(48x)
for k, mult in [(2, 1), (3, 3), (4, 12), (5, 48)]:
    a, b = num(f"_{k}_"), num(f"_{k}__2"); hi, lo = pd.concat([a, b], axis=1).max(axis=1), pd.concat([a, b], axis=1).min(axis=1)
    mid, width = (hi + lo) / 2, (hi - lo)
    m = mid.notna() & (width > 0)
    print(f"\n══ 구름 {k} (≈{mult*5}분)  폭 중앙값 {(width/c*100)[m].median():.3f}%  폭/ATR14 중앙값 {(width/tr.rolling(14).mean())[m].median():.2f} ══")
    best = []
    for name, fn in [("EMA", lambda n: c.ewm(span=n, adjust=False).mean()), ("SMA", lambda n: c.rolling(n).mean()), ("HMA", lambda n: hma(c, n)),
                     ("EMA(hl2)", lambda n: ((h + l) / 2).ewm(span=n, adjust=False).mean())]:
        for n in [int(x * mult) for x in (5, 8, 9, 10, 13, 14, 20, 21, 26, 30, 34, 50, 55)]:
            if n < 2 or n > 3000: continue
            ma = fn(n); mm = m & ma.notna()
            err = ((mid - ma) / c * 100)[mm]
            best.append((err.abs().median(), err.abs().mean(), name, n, np.corrcoef(mid[mm].diff().dropna(), ma[mm].diff().dropna())[0,1] if mm.sum()>100 else 0))
    best.sort()
    for e_med, e_mean, name, n, corr in best[:6]:
        print(f"  중심선≈{name}({n:>4})  |오차| 중앙값 {e_med:.3f}%  평균 {e_mean:.3f}%  변화 상관 {corr:.3f}")
    # 폭 vs 변동성
    for name, vol in [("ATR14", tr.rolling(14).mean()), ("ATR14x"+str(mult), tr.rolling(14 * mult).mean()), ("stdev20", c.rolling(20 * mult).std()), ("|hi-lo|", (h - l).rolling(20 * mult).mean())]:
        mm = m & vol.notna()
        ratio = (width / vol)[mm]
        print(f"  폭/{name:<10} 중앙값 {ratio.median():6.2f}  변동계수 {ratio.std()/ratio.mean():.2f}  상관 {np.corrcoef(width[mm], vol[mm])[0,1]:.3f}")
    # 상/하단이 가격보다 위/아래인 비율, 구름 안 비율
    print(f"  가격 위치: 위 {(c > hi)[m].mean()*100:.0f}%  안 {((c <= hi) & (c >= lo))[m].mean()*100:.0f}%  아래 {(c < lo)[m].mean()*100:.0f}%")
    # 상단/하단 각각이 별도 평균인지 (hi - lo 가 일정한가)
    print(f"  상단-중심 / 폭 비율 중앙값 {((hi-mid)/width)[m].median():.2f} (0.5=대칭)")
