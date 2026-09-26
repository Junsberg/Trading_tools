"""ETH 1분봉 후보 표본 외 검증: 규칙은 7/24~9/26 에서 찾았고, 5/29~7/24 는 처음 보는 구간"""
import sys, pandas as pd
sys.argv = [sys.argv[0], "--tf", "1"]
import screen_cloud as sc
from rule_backtest import backtest, stats, random_baseline, by_period
sys.stdout.reconfigure(encoding="utf-8")
LIM = dict(entry_mode="limit", limit_offset_pct=0.05, fill_window=3)
df, nf = sc.load("ETHUSDT"); split = pd.Timestamp("2026-07-24", tz="UTC").timestamp()
print(f"ETH 1분봉 파일 {nf}개, 봉 {len(df):,}  {pd.to_datetime(df.time.iloc[0],unit='s'):%m-%d} ~ {pd.to_datetime(df.time.iloc[-1],unit='s'):%m-%d}")
regimes, triggers = sc.build(df)
for rn, tn in [("가격>구름5", "구름3 상향돌파"), ("가격>구름3&4", "구름3 상향돌파"), ("정역배열 3-5", "구름3 상향돌파"), ("무필터", "구름3 상향돌파")]:
    bull, bear = regimes[rn]; tl, ts = triggers[tn]; e = (tl & bull).astype(int) - (ts & bear).astype(int)
    print(f"\n── {rn} + {tn} ──")
    for sl, tp, hold in [(0.5, 1.0, 180), (0.8, 1.6, 360), (0.8, 0.8, 180)]:
        kw = dict(sl_pct=sl, tp_pct=tp, max_hold=hold, **LIM)
        tr = backtest(df, e, **kw)
        ins, oos = tr[tr.entry_time >= split], tr[tr.entry_time < split]
        si, so = stats(ins), stats(oos)
        e_oos = e.where(df.time < split, 0); b = random_baseline(df[df.time < split].reset_index(drop=True), e_oos[df.time < split].reset_index(drop=True), seeds=10, **kw)
        print(f"  {sl}/{tp}/{hold:<4} 표본내 n={si['n']:<3} PF {si['pf']:.2f} 누적 {si['cum']:+5.1f}%   │  표본외 n={so['n']:<3} PF {so['pf']:.2f} 누적 {so['cum']:+5.1f}% 승률 {so['win']:.0f}%  (무작위10 평균 {b['pf_mean']:.2f} 최고 {b['pf_max']:.2f})")
    tr = backtest(df, e, sl_pct=0.8, tp_pct=1.6, max_hold=360, **LIM)
    print("  월별(0.8/1.6/360):", by_period(tr, "M")["sum"].round(1).to_dict())
