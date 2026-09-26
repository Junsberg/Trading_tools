"""우리 구름대 (다중 타임프레임 채널) 생성 + 레짐×트리거 스크리닝 (바이낸스 5분봉 3년)

구름 정의 (모두 상위 TF 봉 확정 후 반영, 리페인팅 없음):
  A 고저채널 : 상단 = EMA(high, n), 하단 = EMA(low, n)   (TF 별)
  B 켈트너   : 중심 = EMA(close, n), 상/하단 = 중심 ± k·ATR(n)
사용: python our_cloud.py [data/BTCUSDT_5m_3y.csv] [--kind A|B] [--n 20] [--k 1.0]
"""
import sys
import numpy as np, pandas as pd
from rule_backtest import backtest, stats, random_baseline, by_period

sys.stdout.reconfigure(encoding="utf-8")
args = sys.argv[1:]
opt = lambda name, d: args[args.index(name) + 1] if name in args else d
PATH = next((a for a in args if a.endswith(".csv")), "data/BTCUSDT_5m_3y.csv")
KIND, N, K = opt("--kind", "A"), int(opt("--n", 20)), float(opt("--k", 1.0))
TFS = {1: "5min", 2: "15min", 3: "60min", 4: "240min"}   # 구름 번호 → TF (0번은 안 씀)


def make_clouds(df, kind=KIND, n=N, k=K):
    x = df.copy(); x["dt"] = pd.to_datetime(x.time, unit="s", utc=True); x = x.set_index("dt")
    for c_id, tf in TFS.items():
        r = x[["open", "high", "low", "close"]].resample(tf, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        if kind == "A":
            hi, lo = r.high.ewm(span=n, adjust=False).mean(), r.low.ewm(span=n, adjust=False).mean()
        else:
            tr = pd.concat([r.high - r.low, (r.high - r.close.shift()).abs(), (r.low - r.close.shift()).abs()], axis=1).max(axis=1)
            mid = r.close.ewm(span=n, adjust=False).mean(); atr = tr.ewm(alpha=1 / n, adjust=False).mean()
            hi, lo = mid + k * atr, mid - k * atr
        # 상위 TF 봉은 닫힌 뒤 다음 봉부터 사용 (shift 1) → 5분봉에 ffill
        x[f"hi{c_id}"] = hi.shift(1).reindex(x.index, method="ffill"); x[f"lo{c_id}"] = lo.shift(1).reindex(x.index, method="ffill")
        x[f"mid{c_id}"] = (x[f"hi{c_id}"] + x[f"lo{c_id}"]) / 2
    return x.reset_index(drop=True)


def build(df):
    c, h, l = df.close, df.high, df.low
    hi = {k: df[f"hi{k}"] for k in TFS}; lo = {k: df[f"lo{k}"] for k in TFS}; mid = {k: df[f"mid{k}"] for k in TFS}
    def aligned(ks, up):
        ok = pd.Series(True, index=df.index)
        for a, b in zip(ks[:-1], ks[1:]):
            ok &= (mid[a] > mid[b]) if up else (mid[a] < mid[b])
        return ok
    T = pd.Series(True, index=df.index)
    regimes = {
        "무필터": (T, T),
        "정역배열 1-4": (aligned([1, 2, 3, 4], True), aligned([1, 2, 3, 4], False)),
        "정역배열 2-4": (aligned([2, 3, 4], True), aligned([2, 3, 4], False)),
        "가격>구름3&4": ((c > hi[3]) & (c > hi[4]), (c < lo[3]) & (c < lo[4])),
        "가격>구름4": (c > hi[4], c < lo[4]),
    }
    N20 = 20
    hh = c > h.rolling(N20).max().shift(1); ll = c < l.rolling(N20).min().shift(1)
    touch = {k: ((l <= hi[k]) & (c > hi[k]) & (c.shift(1) > hi[k].shift(1)), (h >= lo[k]) & (c < lo[k]) & (c.shift(1) < lo[k].shift(1))) for k in TFS}
    cross = {k: ((c.shift(1) < hi[k].shift(1)) & (c > hi[k]), (c.shift(1) > lo[k].shift(1)) & (c < lo[k])) for k in TFS}
    triggers = {"돌파20 추종": (hh, ll), "돌파20 페이드": (ll, hh)}
    for k in TFS:
        triggers[f"구름{k} 터치반등"] = touch[k]; triggers[f"구름{k} 상향돌파"] = cross[k]
    return regimes, triggers


def main():
    df = make_clouds(pd.read_csv(PATH))
    print(f"{PATH}  봉 {len(df):,}  구름 {KIND} n={N}{' k='+str(K) if KIND=='B' else ''}")
    regimes, triggers = build(df)
    exits = [(0.8, 1.6, 144), (1.0, 2.0, 288), (1.5, 3.0, 576)]
    LIM = dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3)
    rows = []
    for rn, (bull, bear) in regimes.items():
        for tn, (tl, ts) in triggers.items():
            e = (tl & bull).astype(int) - (ts & bear).astype(int)
            if (e != 0).sum() < 60:
                continue
            for sl, tp, hold in exits:
                kw = dict(sl_pct=sl, tp_pct=tp, max_hold=hold, **LIM)
                tr = backtest(df, e, **kw)
                if len(tr) < 50:
                    continue
                s = stats(tr); b = random_baseline(df, e, seeds=3, **kw)
                mid_t = df.time.iloc[len(df) // 2]; s1, s2 = stats(tr[tr.entry_time < mid_t]), stats(tr[tr.entry_time >= mid_t])
                m = by_period(tr, "M")
                rows.append({"레짐": rn, "트리거": tn, "청산": f"{sl}/{tp}/{hold}", "n": s["n"], "승률": round(s["win"], 1), "PF": round(s["pf"], 2),
                             "누적%": round(s["cum"], 1), "MDD": round(s["mdd"], 1), "전반PF": round(s1["pf"], 2), "후반PF": round(s2["pf"], 2),
                             "흑자월": f"{int((m['sum'] > 0).sum())}/{len(m)}", "무작위max": round(b["pf_max"], 2), "초과": round(s["pf"] - b["pf_max"], 2)})
                print(f"  {rn:<12} {tn:<12} {sl}/{tp}/{hold:<4} n={s['n']:<5} PF {s['pf']:.2f} 전{s1['pf']:.2f}/후{s2['pf']:.2f} 무작위max {b['pf_max']:.2f}", flush=True)
    res = pd.DataFrame(rows); pd.set_option("display.width", 250)
    print("\n══ 상위 20 (초과 순) ══"); print(res.sort_values("초과", ascending=False).head(20).to_string(index=False))
    ok = res[(res.PF > 1.1) & (res.전반PF > 1) & (res.후반PF > 1) & (res.초과 > 0.15)]
    print(f"\n전체 {len(res)} | 기준 통과(PF>1.1, 전·후반>1, 초과>0.15): {len(ok)}")
    if len(ok): print(ok.to_string(index=False))
    res.to_csv(f"reports_our_cloud_{KIND}{N}.csv", index=False)


if __name__ == "__main__":
    main()
