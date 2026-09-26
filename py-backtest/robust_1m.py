"""1분봉 후보 견고성: ETH '구름3 상향돌파+가격>구름5', BTC '구름2 터치반등' — 상대 심볼·전후반·롱숏·대조군10·청산 이웃"""
import sys, glob, numpy as np, pandas as pd
sys.argv = [sys.argv[0], "--tf", "1"]
import screen_cloud as sc
from rule_backtest import backtest, stats, summary, by_period, random_baseline
sys.stdout.reconfigure(encoding="utf-8")
LIM = dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3)
data = {s: sc.load(s)[0] for s in ("BTCUSDT", "ETHUSDT")}
cands = {"구름3 상향돌파 + 가격>구름5": ("가격>구름5", "구름3 상향돌파"), "구름2 터치반등 + 무필터": ("무필터", "구름2 터치반등"), "구름2 터치반등 + 정역배열1-5": ("정역배열 1-5", "구름2 터치반등")}
for cname, (rn, tn) in cands.items():
    print(f"\n════ {cname} ════")
    for sym, df in data.items():
        regimes, triggers = sc.build(df); bull, bear = regimes[rn]; tl, ts = triggers[tn]
        e = (tl & bull).astype(int) - (ts & bear).astype(int)
        print(f"── {sym} ({pd.to_datetime(df.time.iloc[0],unit='s'):%m-%d}~{pd.to_datetime(df.time.iloc[-1],unit='s'):%m-%d}, 신호 {(e!=0).sum()}건) ──")
        for sl, tp, hold in [(0.3, 0.6, 60), (0.5, 1.0, 180), (0.8, 1.6, 360), (1.0, 2.0, 720), (0.5, 1.5, 360), (0.8, 0.8, 180)]:
            kw = dict(sl_pct=sl, tp_pct=tp, max_hold=hold, **LIM); tr = backtest(df, e, **kw)
            if len(tr) < 15: print(f"  {sl}/{tp}/{hold}: n={len(tr)} 부족"); continue
            s = stats(tr); b = random_baseline(df, e, seeds=10, **kw); mid = df.time.iloc[len(df)//2]
            s1, s2 = stats(tr[tr.entry_time < mid]), stats(tr[tr.entry_time >= mid]); L, S = stats(tr[tr.dir > 0]), stats(tr[tr.dir < 0])
            print(f"  {sl}/{tp}/{hold:<4} n={s['n']:<4} PF {s['pf']:.2f} (무작위10 평균 {b['pf_mean']:.2f} 최고 {b['pf_max']:.2f})  누적 {s['cum']:+5.1f}%  전반 {s1['pf']:.2f}/후반 {s2['pf']:.2f}  롱 {L['pf']:.2f}({L['n']})/숏 {S['pf']:.2f}({S['n']})")
