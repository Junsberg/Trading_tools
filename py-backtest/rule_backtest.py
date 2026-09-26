"""규칙 기반 백테스터 (파이썬 엔진 핵심)

입력: 봉 데이터(DataFrame: time/open/high/low/close/volume + 지표 열)
규칙: entries(df) -> Series(+1 롱 / -1 숏 / 0)  — 확정봉에서 신호, 다음 봉부터 진입 시도
진입:
  market : 다음 봉 시가 체결 (테이커 수수료)
  limit  : 신호봉 종가에서 limit_offset_pct 만큼 유리한 가격에 지정가 → fill_window 봉 안에 닿으면 체결 (메이커 수수료)
청산: 손절 % / 익절 % / 최대 보유 봉 / 반대 신호(옵션)
  - 봉 안에서 손절·익절 동시 도달 시 손절 우선(보수적)
  - 익절은 지정가로 보고 메이커 수수료, 손절·시간청산은 테이커 수수료
비용: 수수료 + 슬리피지(시장가 체결에만)

사용 예:
    from rule_backtest import backtest, summary, by_period, random_baseline
    res = backtest(df, entries, sl_pct=1.0, tp_pct=3.0, max_hold=144, entry_mode="limit")
    print(summary(res))
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TAKER = 0.04
MAKER = 0.02


def backtest(df: pd.DataFrame, entries: pd.Series, *, sl_pct: float = 0.5, tp_pct: float = 1.0,
             max_hold: int = 36, entry_mode: str = "market", limit_offset_pct: float = 0.0,
             fill_window: int = 3, taker_pct: float = TAKER, maker_pct: float = MAKER,
             slip_pct: float = 0.01, exit_on_opposite: bool = False,
             fee_pct: float | None = None) -> pd.DataFrame:
    if fee_pct is not None:  # 구버전 호환: 단일 수수료
        taker_pct = maker_pct = fee_pct
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    t = df["time"].to_numpy()
    sig = entries.fillna(0).to_numpy(int)
    n = len(df)
    taker = (taker_pct + slip_pct) / 100
    maker = maker_pct / 100

    trades = []
    i = 0
    while i < n - 1:
        d = sig[i]
        if d == 0:
            i += 1
            continue
        # ── 진입 ──
        if entry_mode == "market":
            ei = i + 1
            raw = o[ei]
            entry = raw * (1 + taker * d)
            entry_fee = "taker"
        else:
            lim = c[i] * (1 - limit_offset_pct / 100 * d)  # 롱은 아래, 숏은 위에 지정가
            ei = None
            for j in range(i + 1, min(i + fill_window, n - 1) + 1):
                if (d > 0 and l[j] <= lim) or (d < 0 and h[j] >= lim):
                    ei = j
                    break
            if ei is None:
                i += 1
                continue
            # 시가가 이미 지정가보다 유리하면 시가 체결
            raw = min(o[ei], lim) if d > 0 else max(o[ei], lim)
            entry = raw * (1 + maker * d)
            entry_fee = "maker"
        sl = raw * (1 - sl_pct / 100 * d) if sl_pct > 0 else None
        tp = raw * (1 + tp_pct / 100 * d) if tp_pct > 0 else None
        reason, xi, px = "time", None, None
        # 체결 봉에서는 체결 이후 움직임만 보므로 손절/익절 판정을 다음 봉부터 시작 (보수적)
        for j in range(ei + 1, min(ei + max_hold, n - 1) + 1):
            if d > 0:
                if sl is not None and l[j] <= sl: reason, xi, px = "sl", j, sl; break
                if tp is not None and h[j] >= tp: reason, xi, px = "tp", j, tp; break
            else:
                if sl is not None and h[j] >= sl: reason, xi, px = "sl", j, sl; break
                if tp is not None and l[j] <= tp: reason, xi, px = "tp", j, tp; break
            if exit_on_opposite and sig[j] == -d:
                reason, xi, px = "flip", j, c[j]; break
        if xi is None:
            xi = min(ei + max_hold, n - 1); px = c[xi]; reason = "time"
        exit_cost = maker if reason == "tp" else taker
        exit_px = px * (1 - exit_cost * d)
        ret = (exit_px / entry - 1) * d
        trades.append({"entry_time": t[ei], "exit_time": t[xi], "dir": d, "entry": entry, "exit": exit_px,
                       "ret_pct": ret * 100, "bars": xi - ei, "reason": reason, "entry_fee": entry_fee})
        i = xi + 1  # 청산 후 다음 봉부터 재진입 가능
    return pd.DataFrame(trades)


def stats(tr: pd.DataFrame) -> dict:
    if tr.empty:
        return {"n": 0, "win": np.nan, "pf": np.nan, "avg": np.nan, "cum": np.nan, "mdd": np.nan}
    r = tr["ret_pct"]
    gp = r[r > 0].sum(); gl = -r[r < 0].sum()
    eq = (1 + r / 100).cumprod()
    return {"n": len(tr), "win": (r > 0).mean() * 100, "pf": gp / gl if gl > 0 else 9.99,
            "avg": r.mean(), "cum": (eq.iloc[-1] - 1) * 100, "mdd": ((eq / eq.cummax()) - 1).min() * 100}


def summary(tr: pd.DataFrame, label: str = "") -> str:
    if tr.empty:
        return f"{label:<22} 거래 없음"
    s = stats(tr)
    reasons = tr["reason"].value_counts().to_dict()
    return (f"{label:<22} n={s['n']:<4} 승률 {s['win']:5.1f}%  PF {s['pf']:4.2f}  "
            f"평균 {s['avg']:+.3f}%  누적 {s['cum']:+6.1f}%  MDD {s['mdd']:5.1f}%  "
            f"롱 {int((tr.dir > 0).sum())}/숏 {int((tr.dir < 0).sum())}  {reasons}")


def by_period(tr: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """구간별(주/월) 안정성 확인"""
    if tr.empty:
        return pd.DataFrame()
    x = tr.copy()
    x["p"] = pd.to_datetime(x["entry_time"], unit="s").dt.to_period(freq)
    g = x.groupby("p")["ret_pct"]
    return pd.DataFrame({"n": g.size(), "avg": g.mean().round(3), "sum": g.sum().round(2), "win%": (g.apply(lambda s: (s > 0).mean()) * 100).round(0)})


def random_baseline(df: pd.DataFrame, entries: pd.Series, seeds: int = 5, mask: pd.Series | None = None, **kw) -> dict:
    """같은 건수·같은 방향 비율·같은 청산 조건으로 무작위 진입했을 때의 평균 성과 (드리프트 대조군)"""
    e = entries.fillna(0)
    n_long = int((e > 0).sum()); n_short = int((e < 0).sum())
    pool = df.index if mask is None else df.index[mask.fillna(False)]
    pfs, avgs = [], []
    for s in range(seeds):
        rng = np.random.default_rng(s)
        re = pd.Series(0, index=df.index)
        pick = rng.choice(pool, size=min(n_long + n_short, len(pool)), replace=False)
        re.iloc[pick[:n_long]] = 1; re.iloc[pick[n_long:]] = -1
        st = stats(backtest(df, re, **kw))
        pfs.append(st["pf"]); avgs.append(st["avg"])
    return {"pf_mean": float(np.nanmean(pfs)), "pf_max": float(np.nanmax(pfs)), "avg_mean": float(np.nanmean(avgs))}
