"""Ultimate 구름대 레짐 × 트리거 스크리닝 (바이비트 5분봉 덤프 사용)

사용: python screen_cloud.py BTCUSDT [ETHUSDT ...] [--tf 1]   (기본 5분봉; --tf 1 이면 1분봉 덤프, 0번 구름 제외)
입력: tv-api/reports/study_ULT_SQ_BYBIT_<SYM>_P_5m_*.csv (dump-study.js 결과, 구간별 병합)
"""
import glob, sys
import numpy as np, pandas as pd
from rule_backtest import backtest, stats, random_baseline, by_period

sys.stdout.reconfigure(encoding="utf-8")
TF = 1 if "--tf" in sys.argv and sys.argv[sys.argv.index("--tf") + 1] == "1" else 5
D = 1440 // TF  # 하루 봉 수


def load(sym):
    fs = sorted(glob.glob(f"../tv-api/reports/study_ULT_SQ_BYBIT_{sym}_P_5m_*.csv" if TF == 5 else f"../tv-api/reports/study_ULT_BYBIT_{sym}_P_1m_*.csv"))
    df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce").ffill().bfill()
    num = lambda c: pd.to_numeric(df[c], errors="coerce").where(lambda v: v.abs() < 1e50).ffill()
    for k in range(6):
        a, b = num(f"_{k}_"), num(f"_{k}__2")
        df[f"hi{k}"] = pd.concat([a, b], axis=1).max(axis=1); df[f"lo{k}"] = pd.concat([a, b], axis=1).min(axis=1)
        df[f"mid{k}"] = (df[f"hi{k}"] + df[f"lo{k}"]) / 2
    return df, len(fs)


def build(df):
    c, h, l = df.close, df.high, df.low
    mid = {k: df[f"mid{k}"] for k in range(6)}; hi = {k: df[f"hi{k}"] for k in range(6)}; lo = {k: df[f"lo{k}"] for k in range(6)}
    def aligned(ks, up):
        ok = pd.Series(True, index=df.index)
        for a, b in zip(ks[:-1], ks[1:]):
            ok &= (mid[a] > mid[b]) if up else (mid[a] < mid[b])
        return ok
    T = pd.Series(True, index=df.index)
    regimes = {
        "무필터": (T, T),
        "정역배열 1-5": (aligned([1, 2, 3, 4, 5], True), aligned([1, 2, 3, 4, 5], False)),
        "정역배열 2-5": (aligned([2, 3, 4, 5], True), aligned([2, 3, 4, 5], False)),
        "정역배열 3-5": (aligned([3, 4, 5], True), aligned([3, 4, 5], False)),
        "가격>구름3&4": ((c > hi[3]) & (c > hi[4]), (c < lo[3]) & (c < lo[4])),
        "가격>구름5": (c > hi[5], c < lo[5]),
        "역방향(정배열에서 숏)": (aligned([2, 3, 4, 5], False), aligned([2, 3, 4, 5], True)),
    }
    N = 20
    hh = c > h.rolling(N).max().shift(1); ll = c < l.rolling(N).min().shift(1)
    touch = {k: ((l <= hi[k]) & (c > hi[k]) & (c.shift(1) > hi[k].shift(1)), (h >= lo[k]) & (c < lo[k]) & (c.shift(1) < lo[k].shift(1))) for k in (0, 1, 2, 3, 4)}
    cross = {k: ((c.shift(1) < hi[k].shift(1)) & (c > hi[k]), (c.shift(1) > lo[k].shift(1)) & (c < lo[k])) for k in (1, 2, 3, 4)}
    rh, rl = h.rolling(D).max(), l.rolling(D).min(); rng = rh - rl
    contr = rng.shift(1) < 0.6 * rng.rolling(5 * D).mean().shift(1)
    triggers = {
        "돌파20 추종": (hh, ll), "돌파20 페이드": (ll, hh),
        **({"구름0 터치반등": touch[0]} if TF == 5 else {}),
        "구름1 터치반등": touch[1], "구름2 터치반등": touch[2], "구름3 터치반등": touch[3], "구름4 터치반등": touch[4],
        "구름1 상향돌파": cross[1], "구름2 상향돌파": cross[2], "구름3 상향돌파": cross[3], "구름4 상향돌파": cross[4],
        "일수축 24h돌파": (contr & (c > rh.shift(1)), contr & (c < rl.shift(1))),
    }
    return regimes, triggers


def main():
    syms = [a for a in sys.argv[1:] if not a.startswith("--") and a != "1"] or ["BTCUSDT"]
    exits = [(1.0, 2.0, 144), (1.5, 3.0, 288), (2.0, 4.0, 576)] if TF == 5 else [(0.3, 0.6, 60), (0.5, 1.0, 180), (0.8, 1.6, 360), (1.0, 2.0, 720)]
    LIM = dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3)
    rows = []
    for sym in syms:
        df, nf = load(sym)
        print(f"{sym} {TF}분봉: 파일 {nf}개, 봉 {len(df):,}  {pd.to_datetime(df.time.iloc[0], unit='s'):%Y-%m-%d} ~ {pd.to_datetime(df.time.iloc[-1], unit='s'):%Y-%m-%d}", flush=True)
        regimes, triggers = build(df)
        for rn, (bull, bear) in regimes.items():
            for tn, (tl, ts) in triggers.items():
                e = (tl & bull).astype(int) - (ts & bear).astype(int)
                if (e != 0).sum() < 40:
                    continue
                for sl, tp, hold in exits:
                    kw = dict(sl_pct=sl, tp_pct=tp, max_hold=hold, **LIM)
                    tr = backtest(df, e, **kw)
                    if len(tr) < 30:
                        continue
                    s = stats(tr); b = random_baseline(df, e, seeds=3, **kw)
                    m = by_period(tr, "M")
                    rows.append({"심볼": sym, "레짐": rn, "트리거": tn, "청산": f"{sl}/{tp}/{hold}", "n": s["n"], "승률": round(s["win"], 1),
                                 "PF": round(s["pf"], 2), "평균%": round(s["avg"], 3), "누적%": round(s["cum"], 1), "MDD": round(s["mdd"], 1),
                                 "흑자월": f"{int((m['sum'] > 0).sum())}/{len(m)}", "무작위max": round(b["pf_max"], 2), "초과": round(s["pf"] - b["pf_max"], 2)})
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    for sym in syms:
        r = res[res.심볼 == sym]
        print(f"\n══ {sym} 상위 15 (무작위 최고치 대비 초과 순) ══")
        print(r.sort_values("초과", ascending=False).head(15).to_string(index=False))
        print(f"  조합 {len(r)}개 | PF>1: {(r.PF > 1).sum()} | 초과>0.15: {(r.초과 > 0.15).sum()}")
    if len(syms) > 1:
        key = ["레짐", "트리거", "청산"]
        both = res.groupby(key).agg(n_sym=("심볼", "size"), PF_min=("PF", "min"), 초과_min=("초과", "min"), 누적_sum=("누적%", "sum")).reset_index()
        both = both[both.n_sym == len(syms)].sort_values("초과_min", ascending=False)
        print("\n══ 모든 심볼에서 동시에 살아남는 조합 (초과 최소값 순) ══")
        print(both.head(15).to_string(index=False))
    res.to_csv(f"reports_screen_cloud_{TF}m.csv", index=False)


if __name__ == "__main__":
    main()
