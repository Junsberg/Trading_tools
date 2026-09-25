"""규칙 기반 백테스터 (파이썬 엔진 핵심)

입력: 봉 데이터(DataFrame: time/open/high/low/close/volume + 지표 열)
규칙: entries(df) -> Series(+1 롱 / -1 숏 / 0)  — 확정봉 종가에서 다음 봉 시가로 진입
청산: 손절 % / 익절 % / 최대 보유 봉 / 반대 신호(옵션) — 봉 안에서 손절·익절 동시 도달 시 손절 우선(보수적)
비용: 수수료(진입+청산) + 슬리피지

사용 예:
    from rule_backtest import backtest, summary
    res = backtest(df, entries, sl_pct=0.5, tp_pct=1.0, max_hold=36)
    print(summary(res))
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def backtest(df: pd.DataFrame, entries: pd.Series, *, sl_pct: float = 0.5, tp_pct: float = 1.0,
             max_hold: int = 36, fee_pct: float = 0.04, slip_pct: float = 0.01,
             exit_on_opposite: bool = False) -> pd.DataFrame:
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t = df["time"].to_numpy()
    sig = entries.fillna(0).to_numpy(int)
    n = len(df)
    cost = (fee_pct + slip_pct) / 100  # 편도

    trades = []
    i = 0
    while i < n - 1:
        d = sig[i]
        if d == 0:
            i += 1
            continue
        ei = i + 1                     # 다음 봉 시가 진입
        entry = o[ei] * (1 + cost * d)
        sl = entry * (1 - sl_pct / 100 * d) if sl_pct > 0 else None
        tp = entry * (1 + tp_pct / 100 * d) if tp_pct > 0 else None
        reason, xi, px = "time", None, None
        for j in range(ei, min(ei + max_hold, n - 1) + 1):
            if d > 0:
                if sl is not None and l[j] <= sl: reason, xi, px = "sl", j, sl; break
                if tp is not None and h[j] >= tp: reason, xi, px = "tp", j, tp; break
            else:
                if sl is not None and h[j] >= sl: reason, xi, px = "sl", j, sl; break
                if tp is not None and l[j] <= tp: reason, xi, px = "tp", j, tp; break
            if exit_on_opposite and j > ei and sig[j] == -d:
                reason, xi, px = "flip", j, c[j]; break
        if xi is None:
            xi = min(ei + max_hold, n - 1); px = c[xi]; reason = "time"
        exit_px = px * (1 - cost * d)
        ret = (exit_px / entry - 1) * d
        trades.append({"entry_time": t[ei], "exit_time": t[xi], "dir": d, "entry": entry, "exit": exit_px,
                       "ret_pct": ret * 100, "bars": xi - ei, "reason": reason})
        i = xi + 1  # 청산 후 다음 봉부터 재진입 가능
    return pd.DataFrame(trades)


def summary(tr: pd.DataFrame, label: str = "") -> str:
    if tr.empty:
        return f"{label:<22} 거래 없음"
    r = tr["ret_pct"]
    gp = r[r > 0].sum(); gl = -r[r < 0].sum()
    pf = gp / gl if gl > 0 else float("inf")
    eq = (1 + r / 100).cumprod()
    dd = ((eq / eq.cummax()) - 1).min() * 100
    reasons = tr["reason"].value_counts().to_dict()
    return (f"{label:<22} n={len(tr):<4} 승률 {(r > 0).mean() * 100:5.1f}%  PF {pf:4.2f}  "
            f"평균 {r.mean():+.3f}%  누적 {(eq.iloc[-1] - 1) * 100:+6.1f}%  MDD {dd:5.1f}%  "
            f"롱 {int((tr.dir > 0).sum())}/숏 {int((tr.dir < 0).sum())}  {reasons}")


def by_period(tr: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """구간별(주/월) 안정성 확인"""
    if tr.empty:
        return pd.DataFrame()
    x = tr.copy()
    x["p"] = pd.to_datetime(x["entry_time"], unit="s").dt.to_period(freq)
    g = x.groupby("p")["ret_pct"]
    return pd.DataFrame({"n": g.size(), "avg": g.mean().round(3), "sum": g.sum().round(2), "win%": (g.apply(lambda s: (s > 0).mean()) * 100).round(0)})
